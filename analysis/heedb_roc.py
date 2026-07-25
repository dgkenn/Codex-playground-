#!/usr/bin/env python3
"""Does burst suppression during sedation explain recovery of consciousness that outlasts the drug?

THE GAP, quoted verbatim from the paper that states it. Safavynia SA, Barra ME, Der Nigoghossian C, Shinnick D,
Waldrop G, Choi JM, Ganglberger W, Shen Q, Doyle K, Walline MC, Westover MB, Brown EN, Fins JJ, Victor J,
Edlow BL, Claassen J, Schiff ND, Thaweethai T. "Determinants of Delayed Recovery of Consciousness After
Analgosedation Discontinuation in the ICU", Crit Care Med 2026, PMID 42294965. Verified against the NCBI
E-utilities record, not a web scrape -- PubMed currently serves a CAPTCHA to automated fetches and the summariser
fabricates plausible content when it hits one (docs/LESSONS.md).

    "Seventy-three percent of patients had RoC before hospital discharge, yet 34% of patients achieving RoC did
     not do so within pharmacologically plausible sedative elimination times."

    "In our cohort, the time to RoC was commonly prolonged beyond that expected from sedation exposures alone.
     These data may aid clinicians and families with expectations of RoC and warrant investigation of
     ALTERNATIVE DETERMINANTS of delayed RoC in this population."

Brown is author 12 and Westover -- whose group built HEEDB and the platform this runs on -- is author 11. The
gap was named by a group that includes the people who built the dataset able to close it. They had 784 COVID
patients from one season and NO EEG.

THE HYPOTHESIS. The alternative determinant is visible on an EEG they did not have. A cortex that enters burst
suppression under ordinary sedative doses is a cortex whose recovery outlasts the drug: suppression at a given
exposure reads out how the brain is RESPONDING, not how much drug is present. So it should predict late recovery
AFTER conditioning on the sedative exposure their pharmacokinetic model already accounts for.

REGISTERED PREDICTIONS, committed before the model is fit.
  R1  PRIMARY. Among patients unconscious at sedation discontinuation, burst suppression on an EEG during the
      sedation episode predicts a LOWER probability of recovering consciousness within 48 h, after adjustment
      for sedation duration and the number of distinct sedatives.
      FALSIFIED IF the coefficient is >= 0, or its interval covers zero with a point estimate above -3 pp.
  R2  SPECIFICITY, and the test that makes this about suppression rather than about being sick. Generalized
      slowing -- an EEG marker of encephalopathy that is NOT cortical suppression -- is entered in the same
      model. Burst suppression's coefficient should remain negative and should be LARGER IN MAGNITUDE than
      slowing's. A paired bootstrap of (BS - slowing) is reported, because "one is significant and the other is
      not" is not a test of a difference and this project has made that error four times.
      FALSIFIED IF the paired difference covers zero.
  R3  DOSE-RESPONSE. Among patients with a measured burden (detector validated out-of-sample here at AUC 0.783),
      probability of 48 h recovery falls monotonically across burden quartiles.
      FALSIFIED IF the quartile gradient is non-monotone or its slope covers zero.

WHAT WOULD MAKE THIS FALSE AND IS NOT FIXABLE BY ADJUSTMENT -- stated before seeing any result:
  * CONFOUNDING BY INDICATION, running in the direction of the hypothesis. Deeply suppressed patients may have
    sedation stopped EARLIER precisely because they look over-sedated, which shortens their drug exposure and
    could produce this association with no causal role for the EEG state. Partially addressed by conditioning on
    sedation duration and by the R2 slowing contrast, NOT eliminated.
  * SEVERITY. Suppression marks sick brains, and sick brains recover slowly for reasons that have nothing to do
    with the suppression itself. This is an association. The H2 test in this project failed exactly here: an ICU
    drug-exposure variable turned out to be a severity proxy (docs/LESSONS.md), and the same risk applies to any
    variable measured on these patients.
  * ASCERTAINMENT of the outcome. A patient with no consciousness assessment after discontinuation is excluded,
    and assessment frequency is not random -- sicker patients are assessed more. Reported, not solved.

DEFINITIONS, fixed here before the data is touched.
  time zero   last administration of a burst-suppression-capable sedative (propofol, midazolam, the barbiturates)
              that is followed by >= 24 h with none -- i.e. discontinuation, matching the source paper's design
  unconscious required at time zero: best motor response < 6 within 12 h before/after, else there is nothing to
              recover and the patient is not at risk
  RoC         first GCS BEST MOTOR RESPONSE == 6 (obeys commands). This is the standard operationalisation of
              recovery of consciousness and is what the DoC and sedation-interruption literature uses.
              Secondary: RASS >= -1.
  outcome     recovered within 48 h of time zero (binary). Death before RoC is a COMPETING RISK and is coded as
              not-recovered, which is the conservative coding for R1.
"""
import csv, glob, os, sys
from collections import defaultdict
from datetime import timedelta

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from heedb_bs_ascertainment import dt
from heedb_bs_specificity import all_eeg_patients

OMOP = os.environ.get("OMOP_OUT", "/tmp/eeg_probe/heedb_omop")
NBOOT = int(os.environ.get("NBOOT", "2000"))
GAP_H = float(os.environ.get("GAP_H", "24"))     # silence defining a discontinuation
WIN_H = float(os.environ.get("WIN_H", "48"))     # recovery window
BS_CAPABLE = ("propofol", "midazolam", "pentobarbital", "thiopental", "phenobarbital")


def load_burden():
    b = {}
    for f in sorted(glob.glob("/tmp/eeg_probe/heedb_bs_burden*.csv")):
        for r in csv.DictReader(open(f)):
            try:
                p, v = int(r["patient"]), float(r["burden"])
            except Exception:
                continue
            if v == v:
                b[p] = max(b.get(p, 0.0), v)
    return b


def lpm(X, y):
    return np.linalg.lstsq(X, y, rcond=None)[0]


def main():
    rng = np.random.default_rng(20260725)

    # ---- sedative administrations -------------------------------------------------------------------
    sed = defaultdict(list)
    with open(os.environ.get("SED_FILE", f"{OMOP}/drug_sedatives.csv")) as fh:
        for r in csv.DictReader(fh):
            v = (r.get("drug_source_value") or "").lower()
            if not any(x in v for x in BS_CAPABLE):
                continue
            t = dt(r.get("drug_exposure_start_datetime"))
            if t is None:
                continue
            try:
                sed[int(r["person_id"])].append(t)
            except Exception:
                continue
    print(f"patients with a BS-capable sedative record: {len(sed):,}")

    # ---- consciousness assessments ------------------------------------------------------------------
    motor, rass = defaultdict(list), defaultdict(list)
    with open(f"{OMOP}/measurement_conscious.csv") as fh:
        for r in csv.DictReader(fh):
            s = (r.get("measurement_source_value") or "").upper()
            t = dt(r.get("measurement_datetime"))
            if t is None:
                continue
            try:
                v = float(r.get("value_as_number") or "nan")
            except Exception:
                continue
            if v != v:
                continue
            try:
                p = int(r["person_id"])
            except Exception:
                continue
            if "BEST MOTOR RESPONSE" in s:
                motor[p].append((t, v))
            elif "RASS" in s:
                rass[p].append((t, v))
    print(f"patients with a motor-response assessment: {len(motor):,}   with RASS: {len(rass):,}")

    # ---- EEG findings -------------------------------------------------------------------------------
    when, bs_lab, slow_lab = eeg_findings()
    burden = load_burden()

    # ---- build the cohort ---------------------------------------------------------------------------
    rows, drop = [], defaultdict(int)
    for p, times in sed.items():
        if p not in motor:
            drop["no motor assessment"] += 1
            continue
        times.sort()
        # discontinuation = a sedative administration followed by >= GAP_H with none
        t0 = None
        for i, t in enumerate(times):
            nxt = times[i + 1] if i + 1 < len(times) else None
            if nxt is None or (nxt - t).total_seconds() >= GAP_H * 3600.0:
                t0 = t
                break
        if t0 is None:
            drop["no discontinuation"] += 1
            continue
        m = sorted(motor[p])
        # must be unconscious at time zero
        near = [v for t, v in m if abs((t - t0).total_seconds()) <= 12 * 3600.0]
        if not near:
            drop["no assessment at t0"] += 1
            continue
        if min(near) >= 6:
            drop["already following commands"] += 1
            continue
        after = [(t, v) for t, v in m if t > t0]
        if not after:
            drop["no assessment after t0"] += 1
            continue
        rec = 1.0 if any(v >= 6 and (t - t0).total_seconds() <= WIN_H * 3600.0 for t, v in after) else 0.0
        dur_h = (t0 - times[0]).total_seconds() / 3600.0
        rows.append(dict(pid=p, rec=rec,
                         bs=1.0 if bs_lab.get(p) else 0.0,
                         slow=1.0 if slow_lab.get(p) else 0.0,
                         logdur=float(np.log1p(max(dur_h, 0.0))),
                         nsed=float(min(len(times), 50)),
                         bur=burden.get(p, float("nan")),
                         has_eeg=1.0 if p in when else 0.0))
    print("\ncohort construction:")
    for k, v in sorted(drop.items(), key=lambda x: -x[1]):
        print(f"   dropped, {k:26s} {v:,}")
    rows = [r for r in rows if r["has_eeg"]]
    n = len(rows)
    print(f"\nANALYSABLE: {n:,} patients with a sedation discontinuation, unconscious at t0, an EEG, "
          f"and a later assessment")
    if n < 300:
        print("*** insufficient -- the feasibility gate in docs/research/40_ROC_PIVOT.md section 7 FAILS.")
        return 1
    y = np.asarray([r["rec"] for r in rows], float)
    nbs = int(sum(r["bs"] for r in rows))
    print(f"   recovered within {WIN_H:.0f} h: {100*y.mean():.1f} %")
    print(f"   burst suppression on EEG: {nbs} ({100*nbs/n:.1f} %)   generalized slowing: "
          f"{int(sum(r['slow'] for r in rows))}")
    if nbs < 50 or nbs > n - 50:
        print("*** burst suppression has too little contrast in this cohort; not interpretable")
        return 1

    # ---- R1 + R2 ------------------------------------------------------------------------------------
    def design(R):
        m = len(R)
        return np.column_stack([np.ones(m)] + [np.asarray([r[k] for r in R], float)
                                               for k in ("bs", "slow", "logdur", "nsed")])
    X = design(rows)
    b = lpm(X, y)
    print(f"\n=== R1/R2: probability of recovery within {WIN_H:.0f} h (LPM, adjusted) ===")
    names = ["burst suppression", "gen. slowing", "log sedation hours", "n sedative admins"]
    boots = defaultdict(list); diff = []
    for _ in range(NBOOT):
        i = rng.integers(0, n, n)
        try:
            b2 = lpm(X[i], y[i])
        except Exception:
            continue
        for j in range(1, 5):
            boots[j].append(b2[j])
        diff.append(abs(b2[1]) - abs(b2[2]))
    for j, nm in enumerate(names, 1):
        lo, hi = np.percentile(boots[j], [2.5, 97.5])
        tag = "   <-- R1: predicted NEGATIVE" if j == 1 else ""
        print(f"   {nm:20s} {100*b[j]:+7.2f} pp [{100*lo:+7.2f},{100*hi:+7.2f}] "
              f"{'*' if (lo>0 or hi<0) else 'ns'}{tag}")
    lo, hi = np.percentile(diff, [2.5, 97.5])
    print(f"   |BS| - |slowing|, paired  {100*(abs(b[1])-abs(b[2])):+7.2f} pp "
          f"[{100*lo:+7.2f},{100*hi:+7.2f}] {'*' if lo>0 else 'ns'}   <-- R2")
    r1 = (b[1] < 0 and np.percentile(boots[1], 97.5) < 0)
    print(f"   R1 {'CONFIRMED' if r1 else 'FALSIFIED'}    R2 {'CONFIRMED' if lo > 0 else 'FALSIFIED'}")

    # ---- R3: dose-response on measured burden -------------------------------------------------------
    hb = [r for r in rows if r["bur"] == r["bur"]]
    print(f"\n=== R3: dose-response on measured burden (n={len(hb)}) ===")
    if len(hb) < 200:
        print("   too few patients with a measured burden; not testable")
        return 0
    xb = np.asarray([r["bur"] for r in hb], float)
    yb = np.asarray([r["rec"] for r in hb], float)
    q = np.percentile(xb, [25, 50, 75])
    prev = None; mono = True
    for lab, sel in (("Q1 lowest", xb <= q[0]), ("Q2", (xb > q[0]) & (xb <= q[1])),
                     ("Q3", (xb > q[1]) & (xb <= q[2])), ("Q4 highest", xb > q[2])):
        if sel.sum() >= 10:
            v = 100 * yb[sel].mean()
            print(f"   {lab:11s} n={int(sel.sum()):4d}  recovered {v:5.1f} %")
            if prev is not None and v > prev + 1e-9:
                mono = False
            prev = v
    Xb = np.column_stack([np.ones(len(hb)), xb])
    sl = []
    for _ in range(NBOOT):
        i = rng.integers(0, len(hb), len(hb))
        try:
            sl.append(float(lpm(Xb[i], yb[i])[1]))
        except Exception:
            continue
    lo3, hi3 = np.percentile(sl, [2.5, 97.5])
    s0 = float(lpm(Xb, yb)[1])
    print(f"   slope per unit burden {100*s0:+.2f} pp [{100*lo3:+.2f},{100*hi3:+.2f}] "
          f"{'*' if (lo3>0 or hi3<0) else 'ns'}")
    print(f"   R3 {'CONFIRMED' if (mono and hi3 < 0) else 'FALSIFIED'} "
          f"(monotone decreasing: {mono}; slope excludes zero and negative: {hi3 < 0})")

    print("\n   Sedation is not randomised and this is an association. Deeply suppressed patients may have")
    print("   sedation stopped earlier because they look over-sedated, which would produce this result with no")
    print("   causal role for the EEG state; the slowing contrast bounds one alternative, not all of them.")
    return 0


def eeg_findings():
    """patient -> earliest EEG time, and whether any report carried bs / generalized slowing."""
    import boto3, io
    from botocore.config import Config
    AP = "arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-credentialed-access-point"
    s3 = boto3.client("s3", region_name="us-east-1",
                      config=Config(s3={"payload_signing_enabled": False}))
    when, bs, slow = {}, {}, {}
    for site in ("S0001", "S0002"):
        try:
            txt = s3.get_object(Bucket=AP,
                                Key=f"EEG/HEEDB_Metadata/{site}_EEG__reports_findings.csv"
                                )["Body"].read().decode("utf-8", "replace")
        except Exception as e:
            print(f"  {site}: {type(e).__name__}")
            continue
        for r in csv.DictReader(io.StringIO(txt)):
            pid = (r.get("BDSPPatientID") or "").strip()
            if not pid.isdigit():
                continue
            p = int(pid)
            t = dt(r.get("EndTime(EEG)") or r.get("StartTime(EEG)") or "")
            if t is not None and (p not in when or t < when[p]):
                when[p] = t
            has = lambda k: (r.get(k) or "").strip() not in ("", "None", "nan")
            bs[p] = bs.get(p, False) or has("bs")
            slow[p] = slow.get(p, False) or has("gen slowing")
    return when, bs, slow


if __name__ == "__main__":
    sys.exit(main())
