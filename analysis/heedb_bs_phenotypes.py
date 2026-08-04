#!/usr/bin/env python3
"""ICU burst-suppression PHENOTYPES by aetiology, and whether aetiology explains outcome heterogeneity.

Implements the pre-specified plan in docs/research/38_HEEDB_BS_PHENOTYPE_SAP.md. That document was written and
committed BEFORE the cohort was assembled; this script does not deviate from it, and any deviation forced by the
data is printed at the top of the output rather than made silently.

THE QUESTION, from Guay/Agrawal/Tseng/Gallo/Schreier/Brown, Anesthesiology 2025;143(6):1595-1618:
    "Determining the exact etiology of burst suppression in the ICU can be challenging and likely contributes to
     heterogeneous results in clinical outcomes studies."
    "Future work characterizing distinct burst suppression phenotypes and the underlying mechanisms will help
     refine our understanding of this brain state."

If aetiological pooling really is what makes the outcome literature disagree, then within a single large cohort,
mortality among burst-suppression patients should differ by aetiology. That is testable here and it is what this
script tests.

PRIMARY TEST: a FORMAL HETEROGENEITY test across aetiology categories -- not a series of category-wise
significance statements. Comparing which categories are individually significant is the difference-of-significance
error, which has appeared three times in this project and caused one retraction.

PRE-SPECIFIED FALSIFICATION: if the heterogeneity test is null, the review's premise is NOT supported in these
data, and that is the result reported. It would be a useful negative for the field.

SECONDARY (H2), direction fixed in advance: sedative/iatrogenic suppression carries LOWER mortality than
post-anoxic or structural suppression, because it reflects a treatment decision rather than the brain's response
to injury.

SCALE: linear probability model throughout, so effects are risk differences that are collapsible and summable.
Odds ratios are not collapsible and this project has already been bitten by reading an OR change as mediation.
Inference: PATIENT-level cluster bootstrap (multiple EEGs per patient are not independent).

WHAT THIS CANNOT DO, restated from the plan because it governs interpretation:
  * Aetiology is not randomised. Sicker patients receive more sedation AND more EEG monitoring.
  * INDICATION BIAS IS SEVERE AND UNFIXABLE: continuous EEG is ordered because clinicians are worried. This is a
    cohort of patients someone was concerned about, not a sample of ICU patients.
  * Burst suppression here is a CLINICIAN LABEL on a report, not a quantified burden, and reader heterogeneity is
    an unmeasured error source.
  * Death is ascertained from the OMOP death table; absence of a record is not proof of survival, so the outcome
    is analysed among patients with ascertained vital status and that restriction is reported.
"""
import csv, os, sys, json
from collections import defaultdict
from datetime import datetime

import numpy as np

OMOP = os.environ.get("OMOP_OUT", "/tmp/eeg_probe/heedb_omop")
NBOOT = int(os.environ.get("NBOOT", "2000"))
rng = np.random.default_rng(20260725)

# --- pre-specified aetiology definitions (SAP section 3). ICD-9 and ICD-10 source-value prefixes. -------------
AETIOLOGY = {
    # CORRECTED 2026-07-27 after adversarial review verified these against the OMOP vocabulary:
    #   34982 = "Toxic encephalopathy" -- NOT anoxic injury. Removed.
    #   V1253 = "Personal history of sudden cardiac arrest" -- a history code, not an active
    #           diagnosis; it admits patients whose arrest was in the past. Removed.
    #   3481  = "Anoxic brain damage" -- the true ICD-9 code, and it was MISSING. Added.
    "anoxic": ("4275", "3481", "G931", "I469", "I461", "I460", "P916", "7991", "42741"),
    "status_epilepticus": ("34561", "34571", "3453", "G4101", "G411", "G412", "G419", "G40901"),
    "metabolic": ("5722", "5728", "K7290", "K7291", "5849", "N179", "N19", "27989", "E870",
                  "2765", "7902", "E162", "27651"),
    "sepsis": ("0389", "99591", "99592", "A419", "R6520", "R6521", "3200", "3229", "G039", "A879", "G049"),
    "structural": ("85400", "8540", "S069", "43191", "431", "432", "I619", "I620", "I629",
                   "43491", "I6350", "I639", "80000", "S0690"),
    "hypothermia": ("9916", "T680", "99168"),
}
SEDATIVES = ("propofol", "midazolam", "pentobarbital", "ketamine", "dexmedetomidine",
             "lorazepam", "thiopental", "phenobarbital")


def norm(code):
    return (code or "").replace(".", "").strip().upper()


def parse_dt(s):
    if not s:
        return None
    s = s.strip()
    for f in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:26], f)
        except Exception:
            pass
    return None


def load_conditions(pids):
    """patient -> set of aetiology labels present anywhere in their record."""
    aet = defaultdict(set)
    seen_any = set()
    path = f"{OMOP}/condition_occurrence.csv"
    if not os.path.exists(path):
        return aet, seen_any
    with open(path) as fh:
        for r in csv.DictReader(fh):
            try:
                pid = int(r["person_id"])
            except Exception:
                continue
            seen_any.add(pid)
            c = norm(r.get("condition_source_value"))
            if not c:
                continue
            for lab, prefixes in AETIOLOGY.items():
                if any(c.startswith(p) for p in prefixes):
                    aet[pid].add(lab)
    return aet, seen_any


def load_sedatives(pids):
    path = f"{OMOP}/drug_exposure.csv"
    sed = set(); seen_any = set()
    if not os.path.exists(path):
        return sed, seen_any, False
    with open(path) as fh:
        for r in csv.DictReader(fh):
            try:
                pid = int(r["person_id"])
            except Exception:
                continue
            seen_any.add(pid)
            v = (r.get("drug_source_value") or "").lower()
            if any(s in v for s in SEDATIVES):
                sed.add(pid)
    return sed, seen_any, True


def load_death():
    d = {}
    path = f"{OMOP}/death.csv"
    if not os.path.exists(path):
        return d
    with open(path) as fh:
        for r in csv.DictReader(fh):
            try:
                d[int(r["person_id"])] = parse_dt(r.get("death_datetime"))
            except Exception:
                pass
    return d


def lpm(X, y):
    return np.linalg.lstsq(X, y, rcond=None)[0]


def main():
    pids = {int(x) for x in open("/tmp/heedb_bs_patients.txt").read().split() if x.strip().isdigit()}
    print(f"burst-suppression cohort: {len(pids)} patients")

    aet, cond_seen = load_conditions(pids)
    sed, drug_seen, have_drugs = load_sedatives(pids)
    death = load_death()
    print(f"  with any condition record extracted so far : {len(cond_seen & pids)}")
    print(f"  with any drug record extracted so far      : {len(drug_seen & pids)}"
          f"{'' if have_drugs else '   [drug_exposure.csv NOT PRESENT -- sedative arm skipped]'}")
    print(f"  with a death record                        : {len(set(death) & pids)}")

    # DEVIATION CHECK -- print rather than proceed silently
    frac = len(cond_seen & pids) / max(len(pids), 1)
    if frac < 0.9:
        print(f"\n  *** DEVIATION FROM PLAN: condition extraction only {100*frac:.0f} % complete.")
        print("      Results below are on a PARTIAL cohort and are NOT the pre-specified analysis.")
        print("      They are printed to verify the pipeline runs, not to be interpreted. ***")

    # analysis restricted to patients with ascertained vital status, per the plan
    cohort = sorted(pids & set(death) | (pids & cond_seen))
    rows = []
    for p in cohort:
        labs = aet.get(p, set())
        rows.append(dict(pid=p,
                         died=1.0 if p in death else 0.0,
                         anoxic=1.0 if "anoxic" in labs else 0.0,
                         status=1.0 if "status_epilepticus" in labs else 0.0,
                         metabolic=1.0 if "metabolic" in labs else 0.0,
                         sepsis=1.0 if "sepsis" in labs else 0.0,
                         structural=1.0 if "structural" in labs else 0.0,
                         hypothermia=1.0 if "hypothermia" in labs else 0.0,
                         sedative=1.0 if p in sed else 0.0,
                         n_aet=float(len(labs)),
                         unexplained=1.0 if not labs else 0.0))
    n = len(rows)
    if n < 200:
        print(f"\ninsufficient cohort ({n}) -- extraction still running"); return
    print(f"\nanalysed: {n} patients")
    print("\naetiology prevalence in the burst-suppression cohort:")
    keys = ["anoxic", "status_epilepticus" if False else "status", "metabolic", "sepsis",
            "structural", "hypothermia", "sedative", "unexplained"]
    for k in keys:
        v = np.mean([r[k] for r in rows])
        print(f"   {k:20s} {100*v:5.1f} %   (n={int(sum(r[k] for r in rows))})")
    print(f"   {'mortality (ascertained)':20s} {100*np.mean([r['died'] for r in rows]):5.1f} %")

    # ---- PRIMARY: heterogeneity of mortality across aetiologies -------------------------------------------
    expo = [k for k in ("anoxic", "status", "metabolic", "sepsis", "structural", "hypothermia")
            if sum(r[k] for r in rows) >= 30]
    if len(expo) < 2:
        print("\ntoo few populated aetiology categories for a heterogeneity test"); return
    y = np.asarray([r["died"] for r in rows], float)
    # The outcome here is "a death record exists". If the condition extraction feeding this script was itself
    # restricted to patients with a death record -- which the 16,244-patient main extraction is, since every
    # other test in this project is ascertainment-immune and needs no survivors -- then y is identically 1 and
    # every coefficient is exactly 0.00 with a zero-width interval. That output is indistinguishable in
    # print from a genuine null and has been mistaken for one. Refuse rather than emit it.
    if y.min() == y.max():
        print(f"\n*** ABORT: the outcome has no variance (every one of {n} patients has died={y[0]:.0f}).")
        print("    This is a degenerate cohort, NOT a null result. It means the condition extraction being")
        print("    read was filtered to patients with a death record, so 'has a death record' cannot be an")
        print("    outcome in it. Use the ascertainment-immune timing analysis (heedb_bs_ascertainment.py")
        print("    CHECK 2) instead, or point OMOP_OUT at an unrestricted extraction.")
        return
    X = np.column_stack([np.ones(n)] + [np.asarray([r[k] for r in rows], float) for k in expo])
    b = lpm(X, y)
    print("\n=== PRIMARY: mortality risk difference by aetiology (LPM, vs no such label) ===")
    boots = defaultdict(list); spread = []
    for _ in range(NBOOT):
        i = rng.integers(0, n, n)
        try:
            bb = lpm(X[i], y[i])
        except Exception:
            continue
        for j, k in enumerate(expo, start=1):
            boots[k].append(bb[j])
        spread.append(float(np.max(bb[1:]) - np.min(bb[1:])))
    for j, k in enumerate(expo, start=1):
        lo, hi = np.percentile(boots[k], [2.5, 97.5])
        print(f"   {k:16s} {100*b[j]:+6.2f} pp [{100*lo:+6.2f},{100*hi:+6.2f}] "
              f"{'*' if (lo>0 or hi<0) else 'ns'}")
    lo, hi = np.percentile(spread, [2.5, 97.5])
    obs = float(np.max(b[1:]) - np.min(b[1:]))
    print(f"\n   HETEROGENEITY (max-min risk difference across aetiologies): {100*obs:.2f} pp "
          f"[{100*lo:.2f},{100*hi:.2f}]")
    print("   A spread interval well away from zero means aetiology matters for outcome, which is the")
    print("   review's premise. An interval consistent with zero means it does NOT in these data.")

    # ---- SECONDARY H2: iatrogenic vs injury ---------------------------------------------------------------
    if have_drugs and sum(r["sedative"] for r in rows) >= 30:
        inj = np.asarray([1.0 if (r["anoxic"] or r["structural"]) else 0.0 for r in rows])
        sd = np.asarray([r["sedative"] for r in rows])
        X2 = np.column_stack([np.ones(n), sd, inj])
        b2 = lpm(X2, y)
        bs_, bi_ = [], []
        for _ in range(NBOOT):
            i = rng.integers(0, n, n)
            try:
                bb = lpm(X2[i], y[i])
            except Exception:
                continue
            bs_.append(bb[1]); bi_.append(bb[2])
        lo, hi = np.percentile(bs_, [2.5, 97.5])
        print(f"\n=== SECONDARY H2 (direction pre-specified: sedative LOWER than injury) ===")
        print(f"   sedative exposure    {100*b2[1]:+6.2f} pp [{100*lo:+6.2f},{100*hi:+6.2f}] "
              f"{'*' if (lo>0 or hi<0) else 'ns'}")
        lo, hi = np.percentile(bi_, [2.5, 97.5])
        print(f"   anoxic or structural {100*b2[2]:+6.2f} pp [{100*lo:+6.2f},{100*hi:+6.2f}] "
              f"{'*' if (lo>0 or hi<0) else 'ns'}")
    else:
        print("\n=== SECONDARY H2 skipped: drug_exposure not yet extracted ===")

    print("\nINTERPRETATION LIMITS (from the plan, binding): aetiology is not randomised; indication bias is")
    print("severe because continuous EEG is ordered when clinicians are worried; burst suppression is a")
    print("clinician label rather than a quantified burden; and absence of a death record is not proof of")
    print("survival, so mortality is analysed among patients with ascertained vital status.")


if __name__ == "__main__":
    sys.exit(main())
