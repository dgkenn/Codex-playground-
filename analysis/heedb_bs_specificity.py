#!/usr/bin/env python3
"""THE SPECIFICITY TEST: is this about BURST SUPPRESSION, or merely about aetiology?

THE OBJECTION, and it is fatal if unanswered. The finding so far is that among burst-suppression patients,
aetiology separates outcome by ~34 percentage points, replicating across two hospitals. But post-anoxic patients
die sooner than status-epilepticus patients whether or not their EEG shows burst suppression. If aetiology
predicts outcome identically in patients WITHOUT burst suppression, then nothing here is about burst suppression
at all — we would have rediscovered that cardiac arrest is lethal, which needs no EEG and no paper.

The claim only means something if burst suppression carries DIFFERENT prognostic weight depending on aetiology,
i.e. if there is an interaction. That is what the review's framing implies — that burst suppression is not one
entity, and that pooling it across aetiologies is why outcome studies disagree — and it is what this file tests.

    cohort      ALL adult EEG patients with condition data and an ascertained death, both BS-labelled and not
    exposure    burst suppression labelled on the EEG (yes/no)
    modifier    pre-specified aetiology category
    outcome     death within 30 days of the EEG, among patients with an ascertained death
                (the ascertainment-immune design: death recording completeness varies by aetiology from
                 32 % to 59 %, so 'has a death record' is not a usable outcome)
    model       death30 ~ BS + aetiology + BS x aetiology, linear probability, patient-level bootstrap

    PRIMARY STATISTIC: the spread of the BS x aetiology INTERACTION terms. This is the extent to which burst
    suppression means different things in different aetiologies.

    PASS: the interaction spread excludes zero -- burst suppression's prognostic meaning depends on aetiology,
          which is the reviewable claim.
    FAIL: the interaction spread includes zero -- burst suppression carries the SAME prognostic weight
          everywhere, the earlier result is just aetiology predicting outcome, and the burst-suppression framing
          must be dropped. That is a real possibility and would be reported as the finding.

Also reported, because it is the honest denominator for any claim of novelty: the MAIN effect of aetiology in
BS-NEGATIVE patients. If that already spans 30+ percentage points, then the BS-positive spread reported earlier
is largely inherited rather than discovered.
"""
import csv, io, os, sys
from collections import defaultdict
from datetime import datetime

import numpy as np

OMOP = os.environ.get("OMOP_OUT", "/tmp/eeg_probe/heedb_omop")
NBOOT = int(os.environ.get("NBOOT", "1500"))
rng = np.random.default_rng(20260725)

AETIOLOGY = {
    # CORRECTED 2026-07-27 after adversarial review verified these against the OMOP vocabulary:
    #   34982 = "Toxic encephalopathy" -- NOT anoxic injury. Removed.
    #   V1253 = "Personal history of sudden cardiac arrest" -- a history code, not an active
    #           diagnosis; it admits patients whose arrest was in the past. Removed.
    #   3481  = "Anoxic brain damage" -- the true ICD-9 code, and it was MISSING. Added.
    "anoxic": ("4275", "3481", "G931", "I469", "I461", "I460", "P916", "7991", "42741"),
    "status": ("34561", "34571", "3453", "G4101", "G411", "G412", "G419", "G40901"),
    "metabolic": ("5722", "5728", "K7290", "K7291", "5849", "N179", "N19", "27989", "E870",
                  "2765", "7902", "E162", "27651"),
    "sepsis": ("0389", "99591", "99592", "A419", "R6520", "R6521", "3200", "3229", "G039", "A879", "G049"),
    "structural": ("85400", "8540", "S069", "43191", "431", "432", "I619", "I620", "I629",
                   "43491", "I6350", "I639", "80000", "S0690"),
}


def norm(c):
    return (c or "").replace(".", "").strip().upper()


def dt(s):
    if not s:
        return None
    s = s.strip()
    for f in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:26], f)
        except Exception:
            pass
    return None


def all_eeg_patients():
    """patient -> (earliest EEG time, whether ANY report carried a burst-suppression label, age, sex)."""
    import boto3
    from botocore.config import Config
    s3 = boto3.client("s3", region_name="us-east-1",
                      config=Config(s3={"payload_signing_enabled": False}))
    C = "arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-credentialed-access-point"
    when = {}; bs = {}; age = {}; fem = {}
    for site in ("S0001", "S0002"):
        key = f"EEG/HEEDB_Metadata/{site}_EEG__reports_findings.csv"
        try:
            txt = s3.get_object(Bucket=C, Key=key)["Body"].read().decode("utf-8", "replace")
        except Exception as e:
            print(f"  {site}: {type(e).__name__}"); continue
        for r in csv.DictReader(io.StringIO(txt)):
            pid = r.get("BDSPPatientID")
            if not pid:
                continue
            try:
                p = int(pid)
            except Exception:
                continue
            t = dt(r.get("EndTime(EEG)") or r.get("StartTime(EEG)") or "")
            if t is None:
                continue
            has_bs = (r.get("bs") or "").strip() not in ("", "None", "nan")
            bs[p] = bs.get(p, False) or has_bs
            if p not in when or t < when[p]:
                when[p] = t
                try:
                    a = float(r.get("AgeAtVisit", "") or "nan")
                    if a == a and 18 <= a <= 110:
                        age[p] = a
                except Exception:
                    pass
                fem[p] = 1.0 if (r.get("SexDSC") == "Female") else 0.0
    return when, bs, age, fem


def main():
    aet = defaultdict(set); cond_seen = set()
    with open(f"{OMOP}/condition_occurrence.csv") as fh:
        for r in csv.DictReader(fh):
            try:
                p = int(r["person_id"])
            except Exception:
                continue
            cond_seen.add(p)
            c = norm(r.get("condition_source_value"))
            for lab, pre in AETIOLOGY.items():
                if c and any(c.startswith(x) for x in pre):
                    aet[p].add(lab)
    death = {}
    with open(f"{OMOP}/death.csv") as fh:
        for r in csv.DictReader(fh):
            try:
                death[int(r["person_id"])] = dt(r.get("death_datetime"))
            except Exception:
                pass
    print("loading EEG reports (all patients, BS-positive and BS-negative)...")
    when, bs, age, fem = all_eeg_patients()
    print(f"  EEG patients with a timestamp: {len(when)}   BS-labelled: {sum(1 for v in bs.values() if v)}")

    rows = []
    for p, t in when.items():
        if p not in cond_seen:
            continue
        d = death.get(p)
        if d is None:
            continue                      # ascertainment-immune: everyone here has a recorded death
        days = (d - t).days
        if days < -1:
            continue
        if p not in age:
            continue
        labs = aet.get(p, set())
        rows.append(dict(bs=1.0 if bs.get(p) else 0.0,
                         d30=1.0 if days <= 30 else 0.0,
                         age=(age[p] - 60.0) / 15.0, fem=fem.get(p, 0.0),
                         **{k: (1.0 if k in labs else 0.0) for k in AETIOLOGY}))
    n = len(rows)
    nbs = int(sum(r["bs"] for r in rows))
    print(f"\nanalysable: {n} patients with ascertained death + EEG time + condition data")
    print(f"   burst-suppression positive: {nbs}   negative: {n - nbs}")
    if n < 1000 or nbs < 200 or (n - nbs) < 200:
        print("insufficient for the interaction test"); return

    expo = [k for k in AETIOLOGY
            if sum(r[k] for r in rows) >= 40
            and sum(r[k] * r["bs"] for r in rows) >= 25
            and sum(r[k] * (1 - r["bs"]) for r in rows) >= 25]
    print(f"aetiologies usable in BOTH BS strata: {expo}")
    if len(expo) < 2:
        print("too few"); return

    def design(R):
        m = len(R)
        cols = [np.ones(m), np.asarray([r["bs"] for r in R])]
        for k in expo:
            cols.append(np.asarray([r[k] for r in R]))
        for k in expo:
            cols.append(np.asarray([r[k] * r["bs"] for r in R]))
        cols += [np.asarray([r["age"] for r in R]), np.asarray([r["fem"] for r in R])]
        return np.column_stack(cols), np.asarray([r["d30"] for r in R], float)

    X, y = design(rows)
    b = np.linalg.lstsq(X, y, rcond=None)[0]
    nE = len(expo)
    main_idx = list(range(2, 2 + nE))
    int_idx = list(range(2 + nE, 2 + 2 * nE))

    print(f"\n=== main effect of aetiology in BS-NEGATIVE patients (the honest denominator) ===")
    for j, k in zip(main_idx, expo):
        print(f"   {k:12s} {100*b[j]:+6.2f} pp")
    print(f"   spread {100*(max(b[main_idx])-min(b[main_idx])):.2f} pp")

    print(f"\n=== BS x aetiology INTERACTION (does suppression mean different things?) ===")
    for j, k in zip(int_idx, expo):
        print(f"   {k:12s} {100*b[j]:+6.2f} pp")
    obs_int = float(max(b[int_idx]) - min(b[int_idx]))
    obs_main = float(max(b[main_idx]) - min(b[main_idx]))

    bi, bm = [], []
    for _ in range(NBOOT):
        i = rng.integers(0, n, n)
        Rs = [rows[j] for j in i]
        try:
            X2, y2 = design(Rs)
            b2 = np.linalg.lstsq(X2, y2, rcond=None)[0]
        except Exception:
            continue
        bi.append(float(max(b2[int_idx]) - min(b2[int_idx])))
        bm.append(float(max(b2[main_idx]) - min(b2[main_idx])))
    if len(bi) < 100:
        print("bootstrap failed"); return
    lo, hi = np.percentile(bm, [2.5, 97.5])
    print(f"\n   aetiology spread in BS-NEGATIVE patients : {100*obs_main:.2f} pp [{100*lo:.2f},{100*hi:.2f}]")
    lo, hi = np.percentile(bi, [2.5, 97.5])
    verdict = ("SPECIFIC -- suppression's prognostic meaning DEPENDS on aetiology" if lo > 0
               else "NOT SPECIFIC -- suppression carries the same weight everywhere; the earlier result is "
                    "aetiology, not burst suppression")
    print(f"   BS x aetiology interaction spread        : {100*obs_int:.2f} pp [{100*lo:.2f},{100*hi:.2f}]")

    # THE DIFFERENCE, tested directly. Reporting two spreads with two intervals and observing that one is
    # larger is the comparison-of-significance shortcut this project has committed four times; that the
    # intervals happen not to overlap is evidence but is not the test. bi and bm are computed from the SAME
    # resample index on every replicate, so differencing them per replicate is a paired bootstrap and is the
    # statistic the specificity claim actually rests on.
    bd = [a - c for a, c in zip(bi, bm)]
    lo_d, hi_d = np.percentile(bd, [2.5, 97.5])
    sig = "*" if lo_d > 0 or hi_d < 0 else "ns"
    print(f"   DIFFERENCE (interaction - main), paired   : {100*(obs_int-obs_main):+.2f} pp "
          f"[{100*lo_d:+.2f},{100*hi_d:+.2f}] {sig}")
    if not (lo_d > 0):
        verdict = ("NOT ESTABLISHED -- the interaction spread is not demonstrably larger than the aetiology "
                   "main effect, so specificity to burst suppression is not shown")
    print(f"\n   VERDICT: {verdict}")
    print("\n   If the interaction spread is null, the burst-suppression framing must be dropped and the")
    print("   finding restated as 'aetiology predicts outcome', which needs no EEG.")


if __name__ == "__main__":
    sys.exit(main())
