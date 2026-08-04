#!/usr/bin/env python3
"""Three candidates that survive the full constraint set, tested together.

The landmark result changed the question. The aetiology excess is EXHAUSTED among 30-day survivors (gap +0.832
from the EEG, +0.217 at a day-30 landmark, -0.206 at day 180), and post-anoxic burst-suppression patients die
40.6 % within three days against 12.5 % of post-anoxic patients without it. So this is a fixed subgroup whose
outcome is largely settled at the recording, not a hazard that keeps accruing. Two candidate mechanisms that
predicted a persistent hazard -- global ischaemic dose causing multi-organ injury, and permanent disability
generating complications -- are refuted by that alone.

Three candidates survive. They are tested here.

  T1  PROVOCATION TEST / RESERVE. Among patients receiving a suppressive drug, FAILING to suppress is evidence
      of a robust brain, so the contrast between suppressed and unsuppressed is sharpest where a challenge is
      being applied. This is the natural reading of a result already in hand and previously treated only as a
      failed prediction: the burst-suppression effect is LARGER with an infusion running in 5 of 5 aetiologies.
      The sharp implication is about DOSE. If suppression is informative as a response to a challenge, then
      suppressing at a LOW dose should be worse than suppressing at a HIGH dose -- the same EEG state means
      something different depending on how much drug it took to produce it.
      FALSIFIED IF, among burst-suppression patients with an active infusion, mortality does not fall as
      administered dose rises.

  T2  INFORMATION REDUNDANCY. Perhaps burst suppression means the same thing everywhere, but in sepsis the rest
      of the clinical picture already predicts death, so the EEG adds little; after anoxia, prognosis is
      genuinely uncertain before the recording. That makes the gap a difference in INCREMENTAL value rather than
      in meaning.
      FALSIFIED IF burst suppression's incremental discrimination over a baseline clinical model is similar in
      the two aetiologies -- which would mean the gap is about the finding itself, not about what was already
      known.

  T3  WHAT DEFINES THE DOOMED SUBGROUP? Now the useful question, and no longer a cross-aetiology one. Within
      post-anoxic burst suppression, what separates the 40.6 % dead within three days from the 18.8 % alive past
      six months? Burden, morphology and coexisting findings are all already measured on exactly these patients.
      This is reported descriptively with discrimination statistics; no prediction is registered because it is
      an exploratory characterisation, and it is labelled as such.

WHY T3 MATTERS MORE THAN IT LOOKS. If the doomed subgroup is simply "very high burden", the finding collapses
into the dose-response already established and the aetiology framing was a detour. If it is NOT explained by
burden, then something distinguishes these patients that is visible on the EEG and is not depth -- which is
where the morphology features, so far prognostically inert, get a second and much better-targeted chance.

NOTE (2026-07-26): the 40.6 % / 18.8 % split quoted here comes from the LEGACY exposure, in which a
patient counted as suppressed if ANY of their recordings said so. Measured at the index recording the
split is 45.6 % / 15.2 % -- a sharper early mass, not a softer one. This script still carries the
legacy aggregation (see docs/research/41_RESULTS_LEDGER.md R289) and its numbers are not corrected.
"""
import csv, glob, io, os, sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from heedb_bs_ascertainment import AETIOLOGY, norm, dt
# The sandbox exports placeholder AWS_* env vars that shadow the real profile -- common/awsenv.py.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.awsenv import sanitize as _aws_sanitize; _aws_sanitize()

OMOP = os.environ.get("OMOP_OUT", "/tmp/eeg_probe/heedb_omop")
NBOOT = int(os.environ.get("NBOOT", "800"))
AP = "arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-credentialed-access-point"
BS_CAPABLE = ("propofol", "midazolam", "pentobarbital", "thiopental", "phenobarbital")
FEATS = ["stereotypy", "alpha_beta", "burst_amp", "burst_dur", "burst_rate"]


def lpm(X, y):
    return np.linalg.lstsq(X, y, rcond=None)[0]


def auc(y, s):
    y = np.asarray(y, float); s = np.asarray(s, float)
    n1 = float(y.sum()); n0 = float(len(y) - n1)
    if n1 == 0 or n0 == 0:
        return float("nan")
    o = np.argsort(s, kind="mergesort"); r = np.empty(len(s), float); r[o] = np.arange(1, len(s) + 1)
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def main():
    rng = np.random.default_rng(20260726)

    aet, cond_seen, ncode = defaultdict(set), set(), defaultdict(int)
    with open(f"{OMOP}/condition_occurrence.csv") as fh:
        for r in csv.DictReader(fh):
            try:
                p = int(r["person_id"])
            except Exception:
                continue
            cond_seen.add(p); ncode[p] += 1
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

    burden, morph = {}, {}
    for f in sorted(glob.glob("/tmp/eeg_probe/heedb_bs_burden*.csv")):
        for r in csv.DictReader(open(f)):
            try:
                p, v = int(r["patient"]), float(r["burden"])
            except Exception:
                continue
            if v == v:
                burden[p] = max(burden.get(p, 0.0), v)
    for f in sorted(glob.glob("/tmp/eeg_probe/heedb_burst_morph*.csv")):
        for r in csv.DictReader(open(f)):
            try:
                p = int(r["patient"])
            except Exception:
                continue
            d = {}
            ok = True
            for k in FEATS:
                try:
                    d[k] = float(r[k])
                except Exception:
                    ok = False
            if ok and all(v == v for v in d.values()):
                morph[p] = d

    import boto3
    from botocore.config import Config
    s3 = boto3.client("s3", region_name="us-east-1",
                      config=Config(s3={"payload_signing_enabled": False}))
    FL = ("bs", "gpd", "lpd", "seizure", "gen slowing", "foc slowing")
    when, F, age = {}, defaultdict(dict), {}
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
            if p not in when or t < when[p]:
                when[p] = t
                try:
                    age[p] = float(r.get("AgeAtVisit") or "nan")
                except Exception:
                    age[p] = float("nan")
            for f in FL:
                F[p][f] = F[p].get(f, False) or ((r.get(f) or "").strip() not in ("", "None", "nan"))

    # active infusion + total administered quantity around the EEG
    active, qty, seen_drug = set(), defaultdict(float), set()
    sedf = f"{OMOP}/drug_sedatives.csv"
    if os.path.exists(sedf):
        for r in csv.DictReader(open(sedf)):
            v = (r.get("drug_source_value") or "").lower()
            if not any(x in v for x in BS_CAPABLE):
                continue
            try:
                p = int(r["person_id"])
            except Exception:
                continue
            seen_drug.add(p)
            t0 = when.get(p)
            s = dt(r.get("drug_exposure_start_datetime"))
            e = dt(r.get("drug_exposure_end_datetime"))
            if t0 is None or s is None:
                continue
            near = (e is not None and s <= t0 <= e) or abs((t0 - s).total_seconds()) <= 4 * 3600
            if near:
                active.add(p)
                try:
                    q = float(r.get("quantity") or "nan")
                    if q == q and q > 0:
                        qty[p] += q
                except Exception:
                    pass

    rows = []
    for p, t0 in when.items():
        if p not in cond_seen:
            continue
        d = death.get(p)
        if d is None:
            continue
        days = (d - t0).days
        if days < -1:
            continue
        a = age.get(p, float("nan"))
        rows.append(dict(pid=p, days=float(days), d30=1.0 if days <= 30 else 0.0,
                         d3=1.0 if days <= 3 else 0.0,
                         bs=1.0 if F[p].get("bs") else 0.0,
                         other=sum(1.0 for k in ("gpd", "lpd", "seizure", "gen slowing", "foc slowing")
                                   if F[p].get(k)),
                         age=(0.0 if a != a else (a - 60.0) / 15.0),
                         ncode=float(min(ncode.get(p, 0), 3000)) / 1000.0,
                         act=1.0 if p in active else 0.0, qty=qty.get(p, float("nan")),
                         bur=burden.get(p, float("nan")), labs=aet.get(p, set()),
                         **{k: morph.get(p, {}).get(k, float("nan")) for k in FEATS}))
    n = len(rows)
    print(f"cohort: {n:,}   with burden {sum(1 for r in rows if r['bur']==r['bur']):,}   "
          f"with morphology {sum(1 for r in rows if r['stereotypy']==r['stereotypy']):,}")

    # ================= T1: does DOSE matter among the suppressed? ==================================
    print("\n" + "=" * 92)
    print("T1  PROVOCATION TEST -- among suppressed patients on a drug, is a LOW dose worse?")
    print("=" * 92)
    for k in ("anoxic", "sepsis", "metabolic"):
        g = [r for r in rows if k in r["labs"] and r["bs"] == 1.0 and r["act"] == 1.0
             and r["qty"] == r["qty"] and r["qty"] > 0]
        if len(g) < 120:
            print(f"   {k:12s} only {len(g)} with a usable quantity; skipped"); continue
        q = np.array([r["qty"] for r in g]); y = np.array([r["d30"] for r in g])
        cut = np.percentile(q, [33, 67])
        cells = []
        for lab, sel in (("low", q <= cut[0]), ("mid", (q > cut[0]) & (q <= cut[1])),
                         ("high", q > cut[1])):
            cells.append(f"{100*y[sel].mean():5.1f}% (n={int(sel.sum()):4d})" if sel.sum() >= 15 else "   n/a")
        print(f"   {k:12s} dose tertile  low {cells[0]}  mid {cells[1]}  high {cells[2]}")
    print("   T1 predicts mortality FALLS as dose rises (suppressing at a low dose implies less reserve).")
    print("   NOTE: OMOP `quantity` is heterogeneous across products and routes, so this is a weak instrument")
    print("   and a null here is uninformative rather than evidence against the mechanism.")

    # ================= T2: incremental value over a baseline clinical model ========================
    print("\n" + "=" * 92)
    print("T2  INFORMATION REDUNDANCY -- how much does burst suppression ADD, by aetiology?")
    print("=" * 92)
    print(f"   {'aetiology':12s} {'n':>6s} {'AUC baseline':>13s} {'AUC + BS':>10s} {'increment':>11s} "
          f"{'raw BS effect':>14s}")
    for k in ("anoxic", "sepsis", "metabolic", "structural", "status"):
        g = [r for r in rows if k in r["labs"]]
        if len(g) < 300:
            continue
        y = np.asarray([r["d30"] for r in g], float)
        if y.sum() < 40 or (len(y) - y.sum()) < 40:
            continue
        Xb = np.column_stack([np.ones(len(g))] + [np.asarray([r[c] for r in g], float)
                                                  for c in ("age", "ncode", "other")])
        Xf = np.column_stack([Xb, np.asarray([r["bs"] for r in g], float)])
        ab, af = auc(y, Xb @ lpm(Xb, y)), auc(y, Xf @ lpm(Xf, y))
        a1 = [r["d30"] for r in g if r["bs"] == 1.0]; a0 = [r["d30"] for r in g if r["bs"] == 0.0]
        raw = np.mean(a1) - np.mean(a0)
        print(f"   {k:12s} {len(g):6d} {ab:12.3f} {af:9.3f} {af-ab:+10.3f} {100*raw:+13.2f}pp")
    print("   T2 is supported if the INCREMENT is similar across aetiologies while the raw effect differs --")
    print("   that would mean the gap reflects what was already known, not what suppression means.")

    # ================= T3: what defines the doomed subgroup? ======================================
    print("\n" + "=" * 92)
    print("T3  WITHIN POST-ANOXIC BURST SUPPRESSION -- what separates death in 3 days from survival past 180?")
    print("=" * 92)
    ga = [r for r in rows if "anoxic" in r["labs"] and r["bs"] == 1.0]
    print(f"   post-anoxic burst-suppression patients: {len(ga):,}  "
          f"(dead by 3 d {100*np.mean([r['d3'] for r in ga]):.1f} %)")
    gb = [r for r in ga if r["bur"] == r["bur"]]
    if len(gb) >= 200:
        y = np.asarray([r["d3"] for r in gb], float)
        b = np.asarray([r["bur"] for r in gb], float)
        q = np.percentile(b, [25, 50, 75])
        print("\n   by measured burden quartile, 3-day death:")
        for lab, sel in (("Q1 lowest", b <= q[0]), ("Q2", (b > q[0]) & (b <= q[1])),
                         ("Q3", (b > q[1]) & (b <= q[2])), ("Q4 highest", b > q[2])):
            if sel.sum() >= 15:
                print(f"      {lab:11s} n={int(sel.sum()):4d}  {100*y[sel].mean():5.1f} %")
        Xb = np.column_stack([np.ones(len(gb)), b])
        print(f"   burden alone, AUC for 3-day death: {auc(y, Xb @ lpm(Xb, y)):.3f}")
        gm = [r for r in gb if r["stereotypy"] == r["stereotypy"]]
        if len(gm) >= 150:
            ym = np.asarray([r["d3"] for r in gm], float)
            Z = {}
            for k in FEATS:
                v = np.asarray([r[k] for r in gm], float)
                Z[k] = (v - v.mean()) / (v.std() if v.std() > 1e-12 else 1.0)
            X1 = np.column_stack([np.ones(len(gm)), np.asarray([r["bur"] for r in gm], float)])
            X2 = np.column_stack([X1] + [Z[k] for k in FEATS])
            a1, a2 = auc(ym, X1 @ lpm(X1, ym)), auc(ym, X2 @ lpm(X2, ym))
            print(f"   n={len(gm)} with morphology: burden alone {a1:.3f}, "
                  f"burden + morphology {a2:.3f}, increment {a2-a1:+.3f}")
            bm = lpm(X2, ym)
            for j, k in enumerate(FEATS, 2):
                print(f"      {k:11s} {100*bm[j]:+7.2f} pp/SD")
    print("\n   EXPLORATORY: no prediction registered. If burden alone separates the doomed subgroup, the")
    print("   aetiology framing was a detour and the dose-response is the finding. If it does not, something")
    print("   else visible on the EEG distinguishes them, and morphology gets a better-targeted second chance.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
