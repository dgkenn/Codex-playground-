#!/usr/bin/env python3
"""CROSS-SITE VALIDATION: does the aetiology-mortality spread replicate in an independent hospital?

WHY THIS IS THE BEST EXTERNAL VALIDATION AVAILABLE. The VitalDB arm of this project cannot be externally
replicated at all — a full survey found no other dataset pairing high-resolution EEG with continuous arterial
pressure. HEEDB is different: it contains TWO INDEPENDENT HOSPITAL SITES (S0001 and S0002) with separate patient
populations, separate EEG services, separate readers applying the burst-suppression label, and separate clinical
practice. A finding that holds in one and fails in the other is a local artefact; a finding that holds in both has
survived a change of institution, of reader, and of case mix.

This is also the design the repository's own pre-registered protocol was built around — hospital-split
confirmation — so the machinery and the discipline already exist here.

WHAT IS REPLICATED. The ascertainment-immune analysis, not the compromised primary. Death-record completeness
varies by aetiology (32.1 % unexplained to 59.4 % anoxic), so "has a death record" is not a usable outcome.
The analysis restricts to patients who ALL have an ascertained death and asks how soon after the EEG they died,
which holds ascertainment constant by construction.

    outcome     death within 30 days of the EEG (and 90 days), among patients with an ascertained death
    exposure    pre-specified aetiology categories from ICD-9/10 source values
    estimand    risk difference (linear probability model — collapsible and summable)
    statistic   the max-min HETEROGENEITY spread across aetiologies, computed separately per site
    inference   patient-level bootstrap within each site, and a bootstrapped BETWEEN-SITE DIFFERENCE in the
                spread so that "the sites agree" is a tested claim rather than an eyeballed one

    PASS: both sites show a clearly positive spread, and their difference is consistent with zero.
    FAIL: one site null, or the between-site difference excludes zero — meaning the effect is
          institution-specific and cannot be generalised.

Comparing two per-site significance verdicts would be the difference-of-significance error, which has appeared
three times in this project and caused one retraction. The between-site difference is therefore bootstrapped
directly, from the same replicates, so the two sites move together.

HONEST NOTE ON WHAT THIS DOES AND DOES NOT BUY. Both sites sit inside one health system and one region, share an
EEG reporting infrastructure, and feed the same OMOP instance. This is cross-SITE, not cross-system, validation.
It rules out single-reader and single-unit artefacts; it does not rule out something common to the whole
institution, nor the indication bias that continuous EEG is ordered when clinicians are worried — that applies
equally at both sites and is not addressed by splitting them.
"""
import csv, io, os, sys
from collections import defaultdict
from datetime import datetime

import numpy as np

OMOP = os.environ.get("OMOP_OUT", "/tmp/eeg_probe/heedb_omop")
NBOOT = int(os.environ.get("NBOOT", "2000"))
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


def eeg_by_site():
    """(patient -> site, patient -> earliest burst-suppression EEG time)."""
    import boto3
    from botocore.config import Config
    s3 = boto3.client("s3", region_name="us-east-1",
                      config=Config(s3={"payload_signing_enabled": False}))
    C = "arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-credentialed-access-point"
    site = {}; when = {}
    for s in ("S0001", "S0002"):
        key = f"EEG/HEEDB_Metadata/{s}_EEG__reports_findings.csv"
        try:
            txt = s3.get_object(Bucket=C, Key=key)["Body"].read().decode("utf-8", "replace")
        except Exception as e:
            print(f"  {s}: {type(e).__name__} {str(e)[:60]}"); continue
        n = 0
        for r in csv.DictReader(io.StringIO(txt)):
            v = (r.get("bs") or "").strip()
            if v in ("", "None", "nan"):
                continue
            pid = r.get("BDSPPatientID")
            t = dt(r.get("EndTime(EEG)") or r.get("StartTime(EEG)") or "")
            if not pid or t is None:
                continue
            try:
                p = int(pid)
            except Exception:
                continue
            n += 1
            # a patient appearing at both sites is assigned to the site of their EARLIEST BS EEG
            if p not in when or t < when[p]:
                when[p] = t; site[p] = s
        print(f"  {s}: {n} burst-suppression reports with a timestamp")
    return site, when


def spread_stats(rows, expo, out):
    n = len(rows)
    y = np.asarray([r[out] for r in rows], float)
    X = np.column_stack([np.ones(n)] + [np.asarray([r[k] for r in rows], float) for k in expo])
    b = np.linalg.lstsq(X, y, rcond=None)[0]
    return float(np.max(b[1:]) - np.min(b[1:])), b, X, y


def main():
    pids = {int(x) for x in open("/tmp/heedb_bs_patients.txt").read().split() if x.strip().isdigit()}
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
    print("EEG site assignment:")
    site, when = eeg_by_site()

    rows_by_site = defaultdict(list)
    for p in sorted(pids & cond_seen):
        d = death.get(p); t = when.get(p); s = site.get(p)
        if d is None or t is None or s is None:
            continue
        days = (d - t).days
        if days < -1:
            continue
        labs = aet.get(p, set())
        rows_by_site[s].append(dict(days=days, d30=1.0 if days <= 30 else 0.0,
                                    d90=1.0 if days <= 90 else 0.0,
                                    **{k: (1.0 if k in labs else 0.0) for k in AETIOLOGY}))
    for s in sorted(rows_by_site):
        print(f"  {s}: {len(rows_by_site[s])} analysable patients "
              f"(ascertained death + EEG time + condition data)")
    sites = [s for s in sorted(rows_by_site) if len(rows_by_site[s]) >= 200]
    if len(sites) < 2:
        print("\nfewer than two sites with sufficient data -- cross-site validation not possible yet"); return

    # exposures populated in BOTH sites, so the same model is fitted either side
    expo = [k for k in AETIOLOGY
            if all(sum(r[k] for r in rows_by_site[s]) >= 25 for s in sites)]
    print(f"\naetiologies populated at both sites: {expo}")

    for out, lab in (("d30", "death within 30 days"), ("d90", "death within 90 days")):
        print(f"\n=== {lab} ===")
        obs = {}
        for s in sites:
            o, b, _, _ = spread_stats(rows_by_site[s], expo, out)
            obs[s] = o
            base = np.mean([r[out] for r in rows_by_site[s]])
            print(f"   --- {s}  (n={len(rows_by_site[s])}, baseline {100*base:.1f} %) ---")
            for j, k in enumerate(expo, start=1):
                print(f"      {k:12s} {100*b[j]:+6.2f} pp")
            print(f"      spread {100*o:.2f} pp")
        boots = {s: [] for s in sites}; diffs = []
        for _ in range(NBOOT):
            vals = {}
            for s in sites:
                R = rows_by_site[s]; n = len(R)
                i = rng.integers(0, n, n)
                Rs = [R[j] for j in i]
                try:
                    o, _, _, _ = spread_stats(Rs, expo, out)
                except Exception:
                    o = np.nan
                vals[s] = o
            if any(v != v for v in vals.values()):
                continue
            for s in sites:
                boots[s].append(vals[s])
            diffs.append(vals[sites[0]] - vals[sites[1]])
        if len(diffs) < 100:
            print("   bootstrap failed"); continue
        for s in sites:
            lo, hi = np.percentile(boots[s], [2.5, 97.5])
            tag = "*" if lo > 0 else "ns"
            print(f"   {s} spread {100*obs[s]:.2f} pp [{100*lo:.2f},{100*hi:.2f}] {tag}")
        lo, hi = np.percentile(diffs, [2.5, 97.5])
        agree = (lo < 0 < hi)
        d = obs[sites[0]] - obs[sites[1]]
        print(f"   BETWEEN-SITE DIFFERENCE in spread: {100*d:+.2f} pp [{100*lo:+.2f},{100*hi:+.2f}]   "
              f"{'sites AGREE' if agree else 'sites DIFFER -- effect is institution-specific'}")
        both = all(np.percentile(boots[s], 2.5) > 0 for s in sites)
        print(f"   VERDICT: {'REPLICATES across sites' if (both and agree) else 'does NOT cleanly replicate'}")

    print("\n   Cross-SITE, not cross-system: both sites share a health system, region, EEG reporting")
    print("   infrastructure and OMOP instance. This rules out single-reader and single-unit artefacts.")
    print("   It does not address indication bias, which applies equally at both sites.")


if __name__ == "__main__":
    sys.exit(main())
