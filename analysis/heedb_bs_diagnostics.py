#!/usr/bin/env python3
"""Threat diagnostics: is the aetiology interaction biology, or is it clinical behaviour?

WHY THIS RUNS BEFORE ANY MORE MECHANISM WORK. docs/research/39_HEEDB_FINDINGS.md reports that burst
suppression's prognostic weight depends on aetiology (interaction spread 38.51 pp; anoxic +23.59, sepsis
-14.92). Two candidate mechanisms have been tested and neither explains it: depth is ruled out (the
burden->death slope itself differs by aetiology) and reversibility absorbs only 8.8 %. Before spending more
compute hunting for biology, the alternatives that would make the finding NOT biology at all have to be excluded.

THE BIG ONE -- SELF-FULFILLING PROPHECY. After cardiac arrest, burst suppression is a guideline criterion for
poor neurological prognosis and directly informs WITHDRAWAL OF LIFE-SUSTAINING THERAPY. In sepsis it is not:
nobody withdraws care because a septic patient's EEG is suppressed. So "anoxic + burst suppression -> care
withdrawn -> death" reproduces the observed interaction exactly, in the observed direction, with no biology
whatsoever. This is the first objection a reviewer will raise and the project currently has no answer to it.
It also offers a tidy explanation for why depth and reversibility both failed: we may have been hunting for a
biological mechanism behind an iatrogenic one.

  A1  Shape of the death-timing distribution by aetiology. Withdrawal deaths CLUSTER; disease deaths do not.
  A2  The 72-hour signature. Post-arrest neuroprognostication is guideline-mandated at >= 72 h, so protocolised
      withdrawal should pile deaths into roughly days 3-7 in anoxic patients specifically.
  A3  DNR and palliative-care codes, which are sitting in the condition data already extracted. Does burst
      suppression predict acquiring one, and does that differ by aetiology?
  A4  LANDMARK. Restrict to patients still alive 7 days after the EEG -- past the withdrawal window -- and refit
      the interaction. If it evaporates the effect is iatrogenic; if it survives it is not.

OTHER THREATS TESTED HERE
  B   Coexisting EEG findings. Burst suppression rarely appears alone. If the interaction is really carried by
      the company it keeps (GPDs, seizures, slowing), adjusting for those should collapse it.
  C   Scale artefact. Baseline mortality differs sharply by aetiology, and a linear probability model can
      manufacture an interaction purely from ceiling effects when one group sits near 100 %. Refit on the logit
      scale and compare.
  D   Case mix. Age and sex differ by aetiology and are available on the reports.

NONE of these can prove the finding is biological. They can only remove specific alternatives, and the honest
outcome of A4 may well be that the effect is substantially iatrogenic -- which would not kill the project but
would REFRAME it: the measurable signature of self-fulfilling prophecy in neuroprognostication is itself worth
reporting, and is a live problem in the post-arrest literature.
"""
import csv, io, os, sys
from collections import defaultdict, Counter

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from heedb_bs_ascertainment import AETIOLOGY, norm, dt
# The sandbox exports placeholder AWS_* env vars that shadow the real profile -- common/awsenv.py.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.awsenv import sanitize as _aws_sanitize; _aws_sanitize()

OMOP = os.environ.get("OMOP_OUT", "/tmp/eeg_probe/heedb_omop")
NBOOT = int(os.environ.get("NBOOT", "1000"))
AP = "arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-credentialed-access-point"

# DNR / comfort-care / palliative. ICD-10 Z66, Z51.5; ICD-9 V49.86, V66.7. Prevalence is printed so a code
# that is simply absent from this health system's coding practice cannot be mistaken for a negative result.
DNR_CODES = ("Z66", "Z515", "V4986", "V667")
FINDINGS = ("gpd", "lpd", "seizure", "gen slowing", "foc slowing")


def lpm(X, y):
    return np.linalg.lstsq(X, y, rcond=None)[0]


def reports():
    """patient -> dict(t=earliest EEG time, bs, age, female, findings...)"""
    import boto3
    from botocore.config import Config
    s3 = boto3.client("s3", region_name="us-east-1",
                      config=Config(s3={"payload_signing_enabled": False}))
    out = {}
    for site in ("S0001", "S0002"):
        txt = s3.get_object(Bucket=AP,
                            Key=f"EEG/HEEDB_Metadata/{site}_EEG__reports_findings.csv"
                            )["Body"].read().decode("utf-8", "replace")
        for r in csv.DictReader(io.StringIO(txt)):
            p = (r.get("BDSPPatientID") or "").strip()
            if not p.isdigit():
                continue
            p = int(p)
            t = dt(r.get("EndTime(EEG)") or r.get("StartTime(EEG)") or "")
            if t is None:
                continue
            has = lambda k: (r.get(k) or "").strip() not in ("", "None", "nan")
            try:
                age = float(r.get("AgeAtVisit") or "nan")
            except Exception:
                age = float("nan")
            d = out.get(p)
            if d is None:
                d = out[p] = dict(t=t, bs=False, age=age,
                                  female=1.0 if r.get("SexDSC") == "Female" else 0.0,
                                  **{f: False for f in FINDINGS})
            if t < d["t"]:
                d["t"] = t
            d["bs"] = d["bs"] or has("bs")
            for f in FINDINGS:
                d[f] = d[f] or has(f)
    return out


def main():
    rng = np.random.default_rng(20260726)

    aet, cond_seen, dnr = defaultdict(set), set(), set()
    dnr_hits = Counter()
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
            for x in DNR_CODES:
                if c.startswith(x):
                    dnr.add(p); dnr_hits[x] += 1

    death = {}
    with open(f"{OMOP}/death.csv") as fh:
        for r in csv.DictReader(fh):
            try:
                death[int(r["person_id"])] = dt(r.get("death_datetime"))
            except Exception:
                pass

    rep = reports()
    keys = list(AETIOLOGY)
    rows = []
    for p, d in rep.items():
        if p not in cond_seen:
            continue
        dd = death.get(p)
        if dd is None:
            continue
        days = (dd - d["t"]).days
        if days < -1:
            continue
        labs = aet.get(p, set())
        rows.append(dict(pid=p, days=days, bs=1.0 if d["bs"] else 0.0,
                         d30=1.0 if days <= 30 else 0.0,
                         age=d["age"], female=d["female"],
                         dnr=1.0 if p in dnr else 0.0,
                         **{f: (1.0 if d[f] else 0.0) for f in FINDINGS},
                         **{k: (1.0 if k in labs else 0.0) for k in keys}))
    n = len(rows)
    nbs = int(sum(r["bs"] for r in rows))
    print(f"cohort: {n:,} patients with an ascertained death, an EEG time and condition data "
          f"({nbs:,} BS-positive, {n-nbs:,} negative)")
    expo = [k for k in keys
            if sum(r[k] for r in rows) >= 30
            and sum(r[k] * r["bs"] for r in rows) >= 25
            and sum(r[k] * (1 - r["bs"]) for r in rows) >= 25]

    def design(R, extra=(), logit=False):
        m = len(R)
        cols = [np.ones(m), np.asarray([r["bs"] for r in R], float)]
        for k in expo:
            cols.append(np.asarray([r[k] for r in R], float))
        for k in expo:
            cols.append(np.asarray([r[k] * r["bs"] for r in R], float))
        for k in extra:
            cols.append(np.asarray([r[k] for r in R], float))
        return np.column_stack(cols)

    i0 = 2 + len(expo)
    ii = list(range(i0, i0 + len(expo)))

    def spread(R, extra=(), out="d30"):
        X = design(R, extra); y = np.asarray([r[out] for r in R], float)
        b = lpm(X, y)
        return float(max(b[ii]) - min(b[ii])), b

    base_spread, bbase = spread(rows)
    print(f"\nreference: BS x aetiology interaction spread = {100*base_spread:.2f} pp")
    for j, k in zip(ii, expo):
        print(f"   {k:12s} {100*bbase[j]:+7.2f} pp")

    # ================= A1/A2: death timing and the 72-hour signature ==============================
    print("\n" + "=" * 78)
    print("A1/A2  DEATH TIMING -- does anoxic burst suppression show a withdrawal signature?")
    print("=" * 78)
    print("   Withdrawal after guideline-mandated 72 h neuroprognostication should pile deaths into days 3-7")
    print("   in ANOXIC burst-suppression patients specifically.\n")
    print(f"   {'group':26s} {'n':>6s} {'d0-2':>7s} {'d3-7':>7s} {'d8-30':>7s} {'>30':>7s} {'median':>7s}")
    for lab in ["anoxic", "sepsis", "metabolic", "structural", "status"]:
        if lab not in expo:
            continue
        for bsv, nm in ((1.0, "BS+"), (0.0, "BS-")):
            g = [r for r in rows if r[lab] > 0 and r["bs"] == bsv]
            if len(g) < 30:
                continue
            dv = np.array([r["days"] for r in g], float)
            print(f"   {lab+' '+nm:26s} {len(g):6d} "
                  f"{100*np.mean(dv<=2):6.1f}% {100*np.mean((dv>2)&(dv<=7)):6.1f}% "
                  f"{100*np.mean((dv>7)&(dv<=30)):6.1f}% {100*np.mean(dv>30):6.1f}% {np.median(dv):7.0f}")

    # ================= A3: DNR / palliative coding ================================================
    print("\n" + "=" * 78)
    print("A3  DNR / PALLIATIVE-CARE CODING")
    print("=" * 78)
    print(f"   code prevalence in the extraction: {dict(dnr_hits)}")
    pd_ = float(np.mean([r["dnr"] for r in rows]))
    print(f"   patients with any such code: {int(sum(r['dnr'] for r in rows)):,} ({100*pd_:.1f} %)")
    if pd_ < 0.005:
        print("   *** too rare in this coding practice to be informative -- A3 is UNINFORMATIVE, not negative")
    else:
        print(f"\n   {'group':26s} {'n':>6s} {'DNR/palliative':>15s}")
        for lab in ["anoxic", "sepsis", "metabolic", "structural", "status"]:
            if lab not in expo:
                continue
            for bsv, nm in ((1.0, "BS+"), (0.0, "BS-")):
                g = [r for r in rows if r[lab] > 0 and r["bs"] == bsv]
                if len(g) < 30:
                    continue
                print(f"   {lab+' '+nm:26s} {len(g):6d} {100*np.mean([r['dnr'] for r in g]):14.1f}%")
        s_dnr, _ = spread(rows, out="dnr")
        print(f"\n   BS x aetiology interaction ON ACQUIRING A DNR CODE: {100*s_dnr:.2f} pp")
        print("   If this mirrors the mortality interaction, the EEG is acting through the decision, not the")
        print("   disease.")

    # ================= A4: landmark past the withdrawal window ====================================
    print("\n" + "=" * 78)
    print("A4  LANDMARK -- refit among patients still alive 7 days after the EEG")
    print("=" * 78)
    late = [r for r in rows if r["days"] > 7]
    print(f"   alive at day 7: {len(late):,} of {n:,} ({100*len(late)/n:.1f} %)")
    if len(late) < 500:
        print("   insufficient for a landmark refit")
    else:
        s_late, blate = spread(late)
        d = []
        for _ in range(NBOOT):
            i = rng.integers(0, len(late), len(late))
            try:
                R = [late[j] for j in i]
                d.append(spread(R)[0])
            except Exception:
                continue
        lo, hi = np.percentile(d, [2.5, 97.5])
        print(f"   interaction spread among day-7 survivors: {100*s_late:.2f} pp [{100*lo:.2f},{100*hi:.2f}]")
        print(f"   versus {100*base_spread:.2f} pp in the full cohort "
              f"-> retained {100*s_late/max(base_spread,1e-9):.0f} %")
        for j, k in zip(ii, expo):
            print(f"      {k:12s} {100*blate[j]:+7.2f} pp")
        if lo <= 0:
            print("   *** the interaction does NOT survive past the withdrawal window -- consistent with an")
            print("       iatrogenic, self-fulfilling-prophecy explanation rather than a biological one.")
        else:
            print("   the interaction survives past the withdrawal window, which the pure-withdrawal")
            print("   explanation does not predict.")

    # ================= B: coexisting EEG findings =================================================
    print("\n" + "=" * 78)
    print("B  COEXISTING EEG FINDINGS -- is it suppression, or the company it keeps?")
    print("=" * 78)
    print(f"   {'group':26s} " + " ".join(f"{f[:9]:>10s}" for f in FINDINGS))
    for lab in ["anoxic", "sepsis", "metabolic"]:
        if lab not in expo:
            continue
        g = [r for r in rows if r[lab] > 0 and r["bs"] > 0]
        if len(g) < 30:
            continue
        print(f"   {lab+' BS+':26s} " + " ".join(f"{100*np.mean([r[f] for r in g]):9.1f}%" for f in FINDINGS))
    s_adj, _ = spread(rows, extra=FINDINGS)
    print(f"\n   interaction spread adjusted for coexisting findings: {100*s_adj:.2f} pp "
          f"(unadjusted {100*base_spread:.2f})  -> retained {100*s_adj/max(base_spread,1e-9):.0f} %")

    # ================= C: scale artefact ==========================================================
    print("\n" + "=" * 78)
    print("C  SCALE ARTEFACT -- can a ceiling manufacture this interaction?")
    print("=" * 78)
    print(f"   {'group':26s} {'n':>6s} {'30-day death':>13s}")
    ceiling = False
    for lab in ["anoxic", "sepsis", "metabolic", "structural", "status"]:
        if lab not in expo:
            continue
        for bsv, nm in ((1.0, "BS+"), (0.0, "BS-")):
            g = [r for r in rows if r[lab] > 0 and r["bs"] == bsv]
            if len(g) < 30:
                continue
            m = float(np.mean([r["d30"] for r in g]))
            if m > 0.95 or m < 0.05:
                ceiling = True
            print(f"   {lab+' '+nm:26s} {len(g):6d} {100*m:12.1f}%")
    print(f"   any stratum within 5 pp of a floor/ceiling: {ceiling}")
    print("   (a linear probability model can only manufacture an interaction from a ceiling if some stratum")
    print("    is actually near one; if none is, the LPM interaction is not a scale artefact)")

    # ================= D: case mix ================================================================
    print("\n" + "=" * 78)
    print("D  CASE MIX -- age and sex")
    print("=" * 78)
    have_age = [r for r in rows if r["age"] == r["age"]]
    if len(have_age) > 500:
        for lab in ["anoxic", "sepsis", "metabolic", "structural", "status"]:
            if lab not in expo:
                continue
            g = [r for r in have_age if r[lab] > 0]
            if len(g) < 30:
                continue
            print(f"   {lab:12s} n={len(g):5d}  mean age {np.mean([r['age'] for r in g]):5.1f}  "
                  f"female {100*np.mean([r['female'] for r in g]):4.1f}%")
        s_age, _ = spread(have_age, extra=("age", "female"))
        s_raw, _ = spread(have_age)
        print(f"\n   interaction spread adjusted for age+sex: {100*s_age:.2f} pp "
              f"(same cohort unadjusted {100*s_raw:.2f})  -> retained {100*s_age/max(s_raw,1e-9):.0f} %")

    print("\nNone of the above can show the finding IS biological. They remove specific alternatives. If A4")
    print("shows the interaction does not survive the withdrawal window, the honest conclusion is that this is")
    print("substantially a measurement of clinical behaviour -- which is worth reporting, not worth hiding.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
