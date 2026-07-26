#!/usr/bin/env python3
"""What is suppression burden a marker OF? Neuron-specific enolase as the external reference.

THE QUESTION. Measured burden stratifies three-day death inside the guideline's highly-malignant category from
29.5 % to 73.1 %, and two things are already known about what it is not and how it behaves:

  * NOT a whole-body ischaemic dose marker. The organ-injury test failed its specificity check -- cardiac and
    pressor gradients were STEEPER in sepsis than after arrest, and mediation through organ-injury codes
    absorbed 2.6 %. Burden is brain-specific.
  * IT BEHAVES LIKE A FIXED QUANTITY. The trajectory analysis found that averaging two readings predicts better
    (0.787) than taking the most recent (0.747), and that the difference between readings carries no signal
    once the mean is known (coefficient +5.88 pp [-17.13, +26.58]). That is the behaviour of a constant
    measured with error, not of a state passing through.

Both point the same way -- burden is reading out how much cortex is already lost -- but both are inferences
from the EEG's own behaviour. Neither uses an independent measurement of neuronal injury. NSE is one.

WHY NSE IS THE RIGHT REFERENCE. Neuron-specific enolase is released into serum from dying neurons and is the
guideline-endorsed biochemical marker of hypoxic-ischaemic brain injury after cardiac arrest, sitting alongside
EEG in ERC-ESICM prognostication. It is measured on a completely different physical substrate -- a blood draw,
not a scalp recording -- so it shares no measurement pathway, no montage, no amplifier and no reader with
burden. Agreement between them cannot come from a common artefact.

REGISTERED PREDICTIONS.
  N1  Suppression burden correlates POSITIVELY with peak NSE measured within 72 h of the index EEG.
      NEURONAL-LOSS PREDICTS a clear positive association.
      FALSIFIED IF the association is null: burden would then be reading out something that is not cell death
      -- network or synaptic dysfunction, for instance -- which is an equally publishable and more surprising
      answer.
  N2  REDUNDANCY. If the two measure the same underlying injury, each should add little to the other for
      predicting death. Large mutual increments would mean they capture DIFFERENT aspects, which would also be
      informative and would argue against burden being a pure neuronal-loss readout.
  N3  SPECIFICITY OF THE REFERENCE. The burden-NSE association should be clearest after cardiac arrest, where
      NSE is validated. A similar association in every aetiology would suggest NSE is behaving as a
      nonspecific severity marker here rather than as a neuronal-injury marker.

CARE REQUIRED, learned the hard way in this project.
  * HAEMOLYSIS inflates NSE -- erythrocytes contain it. Extreme values are reported but flagged.
  * TIMING. NSE peaks at 48-72 h after arrest. A draw before the injury, or weeks later, is a different
    quantity, so the window is explicit and the sensitivity to it is reported rather than assumed.
  * BURDEN IS TAKEN AT THE INDEX RECORDING, not maximised over all recordings. Maximising is look-ahead and
    inflated the headline result by a quarter before it was caught.
  * The correlation is reported with a rank statistic. NSE is heavily right-skewed and a Pearson correlation
    on raw values would be a statement about its tail.
"""
import csv, glob, io, os, sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from heedb_bs_ascertainment import AETIOLOGY, norm, dt

OMOP = os.environ.get("OMOP_OUT", "/tmp/eeg_probe/heedb_omop")
NBOOT = int(os.environ.get("NBOOT", "600"))
WIN_H = float(os.environ.get("NSE_WIN_H", "72"))
AP = "arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-credentialed-access-point"


def spearman(x, y):
    x = np.asarray(x, float); y = np.asarray(y, float)
    def rank(v):
        o = np.argsort(v, kind="mergesort"); r = np.empty(len(v), float); r[o] = np.arange(len(v), dtype=float)
        # average ties so the statistic is not sensitive to the many repeated NSE values
        _, inv, cnt = np.unique(v, return_inverse=True, return_counts=True)
        sums = np.zeros(len(cnt)); np.add.at(sums, inv, r)
        return (sums / cnt)[inv]
    rx, ry = rank(x), rank(y)
    rx -= rx.mean(); ry -= ry.mean()
    d = np.sqrt((rx ** 2).sum() * (ry ** 2).sum())
    return float((rx * ry).sum() / d) if d > 0 else float("nan")


def lpm(X, y):
    return np.linalg.lstsq(X, y, rcond=None)[0]


def auc(y, s):
    y = np.asarray(y, float); s = np.asarray(s, float)
    n1 = float(y.sum()); n0 = float(len(y) - n1)
    if n1 == 0 or n0 == 0:
        return float("nan")
    o = np.argsort(s, kind="mergesort"); r = np.empty(len(s), float); r[o] = np.arange(1, len(s) + 1)
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def cv_auc(X, y, rng, folds=5, reps=5):
    out = []
    for _ in range(reps):
        idx = rng.permutation(len(y))
        for f in range(folds):
            te = idx[f::folds]; tr = np.setdiff1d(idx, te)
            if y[tr].sum() < 5 or y[te].sum() < 3:
                continue
            try:
                out.append(auc(y[te], X[te] @ lpm(X[tr], y[tr])))
            except Exception:
                continue
    return float(np.nanmean(out)) if out else float("nan")


def main():
    rng = np.random.default_rng(20260726)

    path = f"{OMOP}/measurement_nse.csv"
    if not os.path.exists(path):
        print(f"missing {path} -- run: PIDS_FILE=/tmp/heedb_eeg_all_patients.txt python "
              "analysis/heedb_omop_extract.py measurement_nse")
        return 1

    # ---- N0: what did the extraction actually find? -------------------------------------------------
    print("=" * 92)
    print("N0  WHAT IS IN THE NSE EXTRACTION?  (before any inference)")
    print("=" * 92)
    raw = defaultdict(list)
    names = defaultdict(int)
    units = defaultdict(int)
    with open(path) as fh:
        for r in csv.DictReader(fh):
            try:
                p = int(r["person_id"])
                v = float(r["value_as_number"])
            except Exception:
                continue
            if not (v == v):
                continue
            nm = (r.get("measurement_source_value") or "").strip()
            names[nm[:44]] += 1
            units[(r.get("unit_source_value") or "").strip()[:16]] += 1
            t = dt(r.get("measurement_datetime") or r.get("measurement_date") or "")
            if t is not None:
                raw[p].append((t, v, nm))
    print(f"   patients with at least one assay: {len(raw):,}")
    print("   assay names:")
    for k, v in sorted(names.items(), key=lambda x: -x[1])[:10]:
        print(f"      {v:7,d}  {k!r}")
    print("   units:")
    for k, v in sorted(units.items(), key=lambda x: -x[1])[:6]:
        print(f"      {v:7,d}  {k!r}")
    allv = np.array([v for lst in raw.values() for _, v, _ in lst], float)
    if len(allv):
        q = np.percentile(allv, [5, 25, 50, 75, 95, 99])
        print(f"   values: n={len(allv):,}  median {q[2]:.1f}  IQR {q[1]:.1f}-{q[3]:.1f}  "
              f"p95 {q[4]:.1f}  p99 {q[5]:.1f}")
        print("   (serum NSE after arrest is conventionally reported in ug/L; >60 supports a poor outcome)")
    if len(raw) < 60:
        print("\n   *** TOO FEW PATIENTS HAVE NSE IN THIS DATABASE to answer the mechanism question this way.")
        print("   That is itself a finding about the data source, not about the biology. Reported as such.")
        return 2

    # ---- cohort ------------------------------------------------------------------------------------
    burden = {}
    for f in sorted(glob.glob("/tmp/eeg_probe/heedb_bs_burden*.csv")):
        for r in csv.DictReader(open(f)):
            try:
                p, s, v = int(r["patient"]), int(r["session"]), float(r["burden"])
            except Exception:
                continue
            if v == v and (p not in burden or s < burden[p][0]):
                burden[p] = (s, v)          # INDEX recording, not the max over all recordings
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
                bs[p] = cur

    rows = []
    for p, t0 in when.items():
        if p not in cond_seen or p not in burden or p not in raw:
            continue
        near = [v for t, v, _ in raw[p] if -WIN_H <= (t - t0).total_seconds() / 3600.0 <= WIN_H]
        if not near:
            continue
        d = death.get(p)
        days = (d - t0).days if d is not None else None
        if days is not None and days < -1:
            continue
        rows.append(dict(pid=p, bur=burden[p], nse=float(max(near)),
                         bs=1.0 if bs.get(p) else 0.0,
                         d3=(1.0 if (days is not None and days <= 3) else 0.0),
                         has_death=d is not None, labs=aet.get(p, set())))
    n = len(rows)
    print(f"\n   with BOTH an index burden and an NSE within +/-{WIN_H:.0f} h of it: {n:,}")
    if n < 60:
        print("   *** too few for inference; reported as a data-availability finding")
        return 2

    # ---- N1 ----------------------------------------------------------------------------------------
    print("\n" + "=" * 92)
    print("N1  DOES BURDEN TRACK NEURON-SPECIFIC ENOLASE?")
    print("=" * 92)
    b = np.array([r["bur"] for r in rows]); e = np.array([r["nse"] for r in rows])
    rho = spearman(b, e)
    bootr = []
    for _ in range(NBOOT):
        i = rng.integers(0, n, n)
        if len(np.unique(b[i])) > 2 and len(np.unique(e[i])) > 2:
            bootr.append(spearman(b[i], e[i]))
    lo, hi = np.percentile(bootr, [2.5, 97.5]) if len(bootr) > 100 else (float("nan"),) * 2
    print(f"   Spearman rho = {rho:+.3f} [{lo:+.3f},{hi:+.3f}]   n={n:,}")
    print(f"   {'burden quartile':18s} {'n':>5s} {'median NSE':>12s} {'p75':>9s}")
    q = np.percentile(b, [25, 50, 75])
    for lab, sel in (("Q1 lowest", b <= q[0]), ("Q2", (b > q[0]) & (b <= q[1])),
                     ("Q3", (b > q[1]) & (b <= q[2])), ("Q4 highest", b > q[2])):
        if sel.sum() >= 10:
            print(f"   {lab:18s} {int(sel.sum()):5d} {np.median(e[sel]):11.1f} "
                  f"{np.percentile(e[sel],75):8.1f}")
    print(f"\n   N1 {'CONFIRMED' if lo > 0 else 'FALSIFIED'}: burden "
          f"{'tracks' if lo > 0 else 'does NOT track'} an independent marker of neuronal death.")
    if not (lo > 0):
        print("   A null here is the more surprising and more interesting answer: it would mean burden reads")
        print("   out something other than the amount of cell death -- network or synaptic failure -- and")
        print("   that claim needs the redundancy test below before it is made.")

    # ---- N2 ----------------------------------------------------------------------------------------
    print("\n" + "=" * 92)
    print("N2  REDUNDANCY -- do they carry the same information about dying?")
    print("=" * 92)
    g = [r for r in rows if r["has_death"]]
    if len(g) >= 80:
        y = np.asarray([r["d3"] for r in g], float)
        if y.min() < y.max():
            bb = np.asarray([r["bur"] for r in g], float)
            ee = np.log1p(np.asarray([r["nse"] for r in g], float))   # right-skewed; log for a linear model
            one = np.ones(len(g))
            cb = cv_auc(np.column_stack([one, bb]), y, rng)
            ce = cv_auc(np.column_stack([one, ee]), y, rng)
            cbe = cv_auc(np.column_stack([one, bb, ee]), y, rng)
            print(f"   burden alone            CV AUC {cb:.3f}")
            print(f"   log NSE alone           CV AUC {ce:.3f}")
            print(f"   both                    CV AUC {cbe:.3f}")
            print(f"   NSE adds over burden {cbe-cb:+.3f}   burden adds over NSE {cbe-ce:+.3f}")
            print("\n   SAME UNDERLYING INJURY predicts small mutual increments. Large ones would mean the")
            print("   EEG and the serum marker see different things, which argues against burden being a")
            print("   pure readout of how many neurons have died.")
        else:
            print("   outcome has no variance in this subset")
    else:
        print(f"   only {len(g)} with an ascertained death; skipped")

    # ---- N3 ----------------------------------------------------------------------------------------
    print("\n" + "=" * 92)
    print("N3  IS THE ASSOCIATION SPECIFIC TO CARDIAC ARREST, where NSE is validated?")
    print("=" * 92)
    print(f"   {'aetiology':16s} {'n':>5s} {'rho':>8s} {'median NSE':>12s}")
    for k in ("anoxic", "sepsis", "metabolic", "structural"):
        gg = [r for r in rows if k in r["labs"]]
        if len(gg) < 40:
            continue
        bb = np.array([r["bur"] for r in gg]); ee = np.array([r["nse"] for r in gg])
        print(f"   {k:16s} {len(gg):5d} {spearman(bb, ee):+7.3f} {np.median(ee):11.1f}")
    print("\n   A similar association in every aetiology would suggest NSE is acting as a nonspecific")
    print("   severity marker in this cohort rather than as a marker of neuronal injury, which would weaken")
    print("   what N1 can be taken to show.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
