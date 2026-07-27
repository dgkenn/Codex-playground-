#!/usr/bin/env python3
"""Is the reversal ANOXIA-specific, or just anoxic-versus-a-heterogeneous-remainder?

`heedb_content_sign_flip.py` established that intra-burst 8-30 Hz content ranks 30-day death in OPPOSITE
directions in anoxic and non-anoxic patients -- AUC 0.589 [0.545, 0.633] versus 0.408 [0.364, 0.451] -- and
that this survives stratification on burden (3/3) and on burst count, the variable gating the L1 exclusion
(3/3). What it did not establish is whether "non-anoxic" is a category or a leftover. That group pools sepsis,
metabolic, structural and status epilepticus, and a single deviant subgroup could carry the whole contrast.

THE TEST, and it is the sharpest discriminator left. A genuinely anoxia-specific effect predicts the SAME
direction in **every** non-anoxic subgroup, each below 0.5, with anoxia alone above it. A pooled artefact
predicts the opposite: one or two subgroups doing the work while the others sit at chance.

  A1  AUC of intra-burst content for 30-day death within each aetiology separately.
      CONFIRMED IF anoxic is above 0.5 and every non-anoxic subgroup with adequate n is below it.
      FALSIFIED IF the non-anoxic subgroups disagree among themselves -- in which case the contrast is
      between anoxia and one particular other condition, which is a different and much weaker claim.

  A2  The same, restricted to patients with a SINGLE aetiology label, since comorbid coding is common and a
      patient coded both anoxic and septic belongs to neither arm cleanly. This is the stricter version and
      the one to believe if the two disagree.

Sepsis is the subgroup to watch. P7 already records that suppression means *more* after anoxia than after
sepsis (log-odds +0.801 at the EEG), so sepsis is where an aetiology contrast in this project has previously
lived, and a reversal that turns out to be anoxic-versus-septic specifically would be a narrower finding than
the one claimed.
"""
import csv, io, os, sys
from collections import defaultdict
from datetime import datetime

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from icare_morph_replication import auc
from heedb_bs_ascertainment import AETIOLOGY, norm

AP = "arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-credentialed-access-point"
OMOP = os.environ.get("OMOP_OUT", "/tmp/eeg_probe/heedb_omop")
MORPH = os.environ.get("HEEDB_MORPH", "/tmp/eeg_probe/heedb_burst_morph.s*.csv")
CACHE = os.environ.get("AET_FULL_CACHE", "/tmp/eeg_probe/heedb_aetiology_full.csv")
NBOOT = int(os.environ.get("NBOOT", "2000"))
LABELS = ["anoxic", "sepsis", "metabolic", "structural", "status"]


def dt(s):
    s = (s or "").strip()
    for f in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, f)
        except ValueError:
            continue
    return None


def median_by_patient(pattern, col):
    import glob
    d = defaultdict(list)
    for path in sorted(glob.glob(pattern)):
        for r in csv.DictReader(open(path)):
            p = (r.get("patient") or "").strip()
            try:
                v = float(r[col])
            except (KeyError, TypeError, ValueError):
                continue
            if p.isdigit() and v == v:
                d[int(p)].append(v)
    return {p: float(np.median(v)) for p, v in d.items()}


def aetiology_full():
    if os.path.exists(CACHE):
        out = defaultdict(set)
        for r in csv.DictReader(open(CACHE)):
            if r["label"]:
                out[int(r["pid"])].add(r["label"])
        return out
    out = defaultdict(set)
    with open(f"{OMOP}/condition_occurrence.csv") as fh:
        for r in csv.DictReader(fh):
            try:
                p = int(r["person_id"])
            except (KeyError, TypeError, ValueError):
                continue
            c = norm(r.get("condition_source_value"))
            if not c:
                continue
            for lab, pre in AETIOLOGY.items():
                if any(c.startswith(x) for x in pre):
                    out[p].add(lab)
    with open(CACHE, "w", newline="") as f:
        w = csv.writer(f); w.writerow(["pid", "label"])
        for p, labs in out.items():
            for l in labs:
                w.writerow([p, l])
    return out


def auc_ci(y, s, rng, reps):
    n = len(y); o = []
    for _ in range(reps):
        i = rng.integers(0, n, n)
        if 0 < y[i].sum() < n:
            a = auc(y[i], s[i])
            if a == a:
                o.append(a)
    if len(o) < 50:
        return float("nan"), float("nan")
    return tuple(np.percentile(o, [2.5, 97.5]))


def main():
    rng = np.random.default_rng(20260727)
    import boto3
    from botocore.config import Config
    s3 = boto3.client("s3", region_name="us-east-1",
                      config=Config(s3={"payload_signing_enabled": False}))
    when = {}
    for st in ("S0001", "S0002"):
        txt = s3.get_object(Bucket=AP,
                            Key=f"EEG/HEEDB_Metadata/{st}_EEG__reports_findings.csv"
                            )["Body"].read().decode("utf-8", "replace")
        for r in csv.DictReader(io.StringIO(txt)):
            p = (r.get("BDSPPatientID") or "").strip()
            if not p.isdigit():
                continue
            t = dt(r.get("EndTime(EEG)") or r.get("StartTime(EEG)") or "")
            p = int(p)
            if t and (p not in when or t < when[p]):
                when[p] = t
    death = {}
    with open(f"{OMOP}/death.csv") as fh:
        for r in csv.DictReader(fh):
            try:
                death[int(r["person_id"])] = dt(r.get("death_datetime"))
            except (KeyError, TypeError, ValueError):
                pass

    aet = aetiology_full()
    ab = median_by_patient(MORPH, "alpha_beta")
    assert ab, "morphology table empty"

    rec = []
    for p, v in ab.items():
        if p in when and p in death and death[p] is not None:
            d = (death[p] - when[p]).days
            if d >= -1:
                rec.append((p, 1.0 if d <= 30 else 0.0, v, aet.get(p, set())))
    assert len(rec) >= 300, f"only {len(rec)} patients"
    print(f"cohort: {len(rec):,} patients with intra-burst content and an ascertained death")

    for title, strict in (("A1  ANY label (patients may carry several)", False),
                          ("A2  SINGLE label only (the stricter version)", True)):
        print("\n" + "=" * 96)
        print(title)
        print("=" * 96)
        print(f"{'aetiology':>12} {'n':>6} {'30-d death':>11} {'AUC':>7} {'95% CI':>18}   direction")
        print("-" * 96)
        res = {}
        for lab in LABELS:
            sel = [r for r in rec if (r[3] == {lab}) if strict] if strict else \
                  [r for r in rec if lab in r[3]]
            if len(sel) < 60:
                print(f"{lab:>12} {len(sel):>6}   too few")
                continue
            y = np.array([r[1] for r in sel]); a = np.array([r[2] for r in sel])
            if not (0 < y.sum() < len(y)):
                print(f"{lab:>12} {len(sel):>6}   no outcome variation")
                continue
            A = auc(y, a); lo, hi = auc_ci(y, a, rng, NBOOT)
            res[lab] = (A, lo, hi)
            print(f"{lab:>12} {len(sel):>6} {100*y.mean():>10.1f}% {A:>7.3f} [{lo:>6.3f},{hi:>6.3f}]"
                  f"   {'higher content -> MORE death' if A > 0.5 else 'higher content -> LESS death'}")
        if "anoxic" in res:
            others = {k: v for k, v in res.items() if k != "anoxic"}
            below = [k for k, v in others.items() if v[0] < 0.5]
            print(f"\n   anoxic AUC {res['anoxic'][0]:.3f}; non-anoxic subgroups below 0.5: "
                  f"{len(below)}/{len(others)}  {sorted(below)}")
            if others and len(below) == len(others) and res["anoxic"][0] > 0.5:
                print("   CONFIRMED -- every non-anoxic subgroup runs the same way and anoxia alone reverses.")
                print("   The contrast is anoxia versus everything else, not anoxia versus one condition.")
            elif others:
                disagree = [k for k in others if k not in below]
                print(f"   NOT confirmed -- these non-anoxic subgroups do NOT run below 0.5: {sorted(disagree)}.")
                print("   The claim narrows to anoxia versus the subgroups that do, which is weaker than")
                print("   'the meaning of burst content depends on aetiology'.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
