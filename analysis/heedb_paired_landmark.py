#!/usr/bin/env python3
"""The visible-versus-invisible comparison, on IDENTICAL patients. The obvious version of this test does not
exist, and finding out why changed what the invisible measure is a claim about.

WHAT WENT WRONG IN R408, STATED FIRST. R408 compared burst suppression's landmark curve (n = 9,302) against
the intra-burst measure's (n = 2,449) and read a difference in ONSET off the two. Those are different
patients, so the comparison is confounded with case mix. The repair was supposed to be a paired estimate on
patients carrying both.

**That repair is impossible, and the reason is the interesting part.** Burst-suppression flag prevalence in
the burst-morphology subcohort is 100.0 % (2,473 of 2,473) against 14.9 % overall — burst morphology can only
be measured on a recording that has bursts. Inside the stratum that carries the invisible measure the flag
has NO VARIANCE, so its interaction is undefined there at any sample size.

So the invisible measure was never a competitor to burst suppression. **It grades what is inside it.** Every
patient carrying it already triggers the guideline's flagship malignant pattern; the measure separates them
further. That is a stronger claim than the one R407 made, and it needs a control that actually varies in the
same stratum.

------------------------------------------------------------------------------------------------------------
REGISTERED, before the paired data was looked at.

  Z0  DOCUMENT THE STRUCTURE. Report flag prevalence inside the morphology subcohort against the full
      findings cohort, so the 100 % is on the record rather than inferred.

  Z1  PAIRED SWEEP. Restrict to the morphology subcohort. On these identical patients, run the R408 landmark
      sweep for the invisible measure AND for every visible flag that retains variance there (GPD, seizure,
      generalized slowing, LPD, focal slowing). Same matched null: subsamples of the same stratum matched on
      n, 30-day death rate and anoxic fraction, with no landmark applied.

  Z2  PRIMARY, and it is a paired comparison this time. Inside the withdrawal window (landmarks 0-3), does
      the invisible measure hold its aetiology interaction while the visible flags in the SAME patients lose
      theirs?
        CONFIRMED IF the invisible measure stays inside its matched null at every landmark 0-3 while at least
        one visible flag falls below its own null across that range.
        FALSIFIED IF the invisible measure falls below its null inside the window, or if no visible flag
        does — either way the window contrast in R408 was cohort, not predictor.

  Z3  DIRECT PAIRED CONTRAST. Bootstrap patients (paired: the same resampled patients supply both estimates)
      and report the fraction of resamples in which the invisible measure retains MORE of its interaction
      than each visible flag at day 3. A ratio has heavy tails, so the reported statistic is this rank
      comparison, not a difference of means.

WHAT A POSITIVE MEANS. That within patients who all carry the guideline's malignant pattern, a measure no
clinician sees holds aetiology-specific prognostic information across the window in which the visible
co-findings lose theirs.
WHAT IT CANNOT MEAN. Anything about burst suppression's own curve, which this design cannot estimate. R408's
onset contrast stays confounded whatever this returns.
"""
import csv, glob, io, os, sys
from collections import defaultdict
from datetime import datetime

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.awsenv import sanitize as _aws_sanitize; _aws_sanitize()
from icare_morph_replication import logit_fit
from heedb_bs_ascertainment import AETIOLOGY, norm

AP = "arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-credentialed-access-point"
OMOP_OLD = os.environ.get("OMOP_OUT", "/tmp/eeg_probe/heedb_omop")
OMOP_Q = os.environ.get("OMOP_QUANT", "/tmp/eeg_probe/heedb_omop_quant")
MORPH = os.environ.get("HEEDB_MORPH", "/tmp/eeg_probe/heedb_burst_morph.s*.csv")
NNULL = int(os.environ.get("NNULL", "200"))
NBOOT = int(os.environ.get("NBOOT", "800"))
LANDMARKS = [0, 1, 2, 3, 5, 7, 10, 14]
FLAGS = ["bs", "gpd", "lpd", "seizure", "gen slowing", "foc slowing"]
INV = "intra-burst 8-30 Hz"
MIN_PREV = 0.05          # a flag needs real variance in the stratum to be a control


def dt(s):
    s = (s or "").strip()
    for f in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, f)
        except ValueError:
            continue
    return None


def load():
    import boto3
    from botocore.config import Config
    s3 = boto3.client("s3", region_name="us-east-1",
                      config=Config(s3={"payload_signing_enabled": False}))
    find, when = defaultdict(dict), {}
    for st in ("S0001", "S0002"):
        txt = s3.get_object(Bucket=AP,
                            Key=f"EEG/HEEDB_Metadata/{st}_EEG__reports_findings.csv"
                            )["Body"].read().decode("utf-8", "replace")
        for r in csv.DictReader(io.StringIO(txt)):
            p = (r.get("BDSPPatientID") or "").strip()
            if not p.isdigit():
                continue
            p = int(p)
            for f in FLAGS:
                find[p][f] = find[p].get(f, False) or (
                    (r.get(f) or "").strip() not in ("", "None", "nan"))
            t = dt(r.get("EndTime(EEG)") or r.get("StartTime(EEG)") or "")
            if t and (p not in when or t < when[p]):
                when[p] = t
    death = {}
    with open(f"{OMOP_OLD}/death.csv") as fh:
        for r in csv.DictReader(fh):
            d = dt(r.get("death_datetime"))
            if d is not None:
                try:
                    death[int(r["person_id"])] = d
                except (KeyError, TypeError, ValueError):
                    pass
    src = f"{OMOP_Q}/condition_occurrence.csv"
    assert os.path.exists(src), f"{src} missing -- rebuild the quant OMOP cache first"
    anox = {}
    with open(src) as fh:
        for r in csv.DictReader(fh):
            try:
                p = int(r["person_id"])
            except (KeyError, TypeError, ValueError):
                continue
            anox.setdefault(p, False)
            c = norm(r.get("condition_source_value"))
            if c and any(c.startswith(x) for x in AETIOLOGY["anoxic"]):
                anox[p] = True
    ab = defaultdict(list)
    for path in sorted(glob.glob(MORPH)):
        for r in csv.DictReader(open(path)):
            p = (r.get("patient") or "").strip()
            try:
                v = float(r["alpha_beta"])
            except (KeyError, TypeError, ValueError):
                continue
            if p.isdigit() and v == v:
                ab[int(p)].append(v)
    ab = {p: float(np.median(v)) for p, v in ab.items()}
    assert len(ab) > 500, f"morphology cache looks empty: {len(ab)} patients"
    return find, when, death, anox, ab


def main():
    rng = np.random.default_rng(20260728)
    find, when, death, anox, ab = load()

    # ---- Z0 ---------------------------------------------------------------------------------------
    print("=" * 100)
    print("Z0  WHY THE OBVIOUS PAIRED TEST DOES NOT EXIST — flag prevalence by stratum")
    print("=" * 100)
    morph_ids = [p for p in ab if p in find]
    print(f"   full findings cohort {len(find):,}      burst-morphology subcohort {len(morph_ids):,}")
    print(f"   {'flag':>14} {'overall':>10} {'in morph subcohort':>20}   usable as a paired control?")
    usable = []
    for f in FLAGS:
        a = np.mean([1.0 if find[p][f] else 0.0 for p in find])
        b = np.mean([1.0 if find[p][f] else 0.0 for p in morph_ids])
        ok = MIN_PREV <= b <= 1 - MIN_PREV
        if ok:
            usable.append(f)
        print(f"   {f:>14} {100*a:>9.1f}% {100*b:>19.1f}%   "
              f"{'yes' if ok else 'NO — no variance in this stratum'}")
    assert "bs" not in usable, "bs unexpectedly varies here; the premise of this script has changed"

    # ---- cohort ------------------------------------------------------------------------------------
    rows = []
    for p in morph_ids:
        if p not in anox or p not in when:
            continue
        d = death.get(p)
        days = (d - when[p]).days if d is not None else None
        if days is not None and days < -1:
            continue
        rows.append((p, days, 1.0 if anox[p] else 0.0, ab[p]))
    n = len(rows)
    y = np.array([0.0 if r[1] is None else (1.0 if r[1] <= 30 else 0.0) for r in rows])
    ax = np.array([r[2] for r in rows])
    dday = np.array([1e9 if r[1] is None else float(r[1]) for r in rows])
    preds = {f: np.array([1.0 if find[r[0]][f] else 0.0 for r in rows]) for f in usable}
    preds[INV] = np.array([r[3] for r in rows])
    print(f"\n   paired cohort {n:,}   30-day death {100*y.mean():.1f}%   anoxic {100*ax.mean():.1f}%")
    print("   every one of these patients carries the burst-suppression flag.")

    def inter(v, m):
        k = int(m.sum())
        if k < 250 or not (0 < y[m].sum() < k):
            return None
        X = np.column_stack([np.ones(k), ax[m], v[m], v[m] * ax[m]])
        try:
            c = float(logit_fit(X, y[m])[3])
        except Exception:
            return None
        return c if np.isfinite(c) else None

    everyone = np.ones(n, bool)
    base = {f: inter(v, everyone) for f, v in preds.items()}

    # ---- Z1 ----------------------------------------------------------------------------------------
    print("\n" + "=" * 100)
    print("Z1 / Z2  PAIRED LANDMARK SWEEP — identical patients throughout")
    print("=" * 100)
    obs, null = defaultdict(dict), defaultdict(dict)
    order = [INV] + usable
    for f in order:
        if base[f] is None or abs(base[f]) < 1e-9:
            print(f"\n  {f}: full-cohort interaction not estimable — skipped")
            continue
        v = preds[f]
        print(f"\n  {f}   {'(INVISIBLE)' if f == INV else '(visible)'}   "
              f"full-cohort interaction {base[f]:+.3f}")
        print(f"    {'landmark':>9} {'n':>6} {'death%':>7} {'observed':>10} "
              f"{'matched null (5-95%)':>26} {'gap':>8}")
        for L in LANDMARKS:
            m = dday > L
            b = inter(v, m)
            if b is None:
                continue
            obs[f][L] = b / base[f]
            tgt = int(m.sum())
            vals = []
            if 250 <= tgt < n:
                cells = {(yy, aa): np.flatnonzero((y == yy) & (ax == aa))
                         for yy in (0.0, 1.0) for aa in (0.0, 1.0)}
                want = {k: int(((y[m] == k[0]) & (ax[m] == k[1])).sum()) for k in cells}
                if all(want[k] <= len(cells[k]) for k in cells):
                    for _ in range(NNULL):
                        idx = np.concatenate([rng.choice(cells[k], want[k], replace=False)
                                              for k in cells if want[k] > 0])
                        mm = np.zeros(n, bool); mm[idx] = True
                        b2 = inter(v, mm)
                        if b2 is not None:
                            vals.append(b2 / base[f])
            if len(vals) >= 30:
                nm, lo, hi = (float(np.median(vals)), float(np.percentile(vals, 5)),
                              float(np.percentile(vals, 95)))
                null[f][L] = (nm, lo, hi)
                s = f"{100*nm:>7.0f}% [{100*lo:>4.0f}%,{100*hi:>4.0f}%]"
                below = "  BELOW" if obs[f][L] < lo else ""
                print(f"    {'day '+str(L):>9} {int(m.sum()):>6,} {100*y[m].mean():>6.1f}% "
                      f"{100*obs[f][L]:>9.0f}% {s:>26} {100*(obs[f][L]-nm):>+7.0f}%{below}")
            else:
                print(f"    {'day '+str(L):>9} {int(m.sum()):>6,} {100*y[m].mean():>6.1f}% "
                      f"{100*obs[f][L]:>9.0f}% {'(null not estimable)':>26}")

    # ---- Z3 paired bootstrap at day 3 ---------------------------------------------------------------
    print("\n" + "=" * 100)
    print("Z3  PAIRED BOOTSTRAP AT DAY 3 — same resampled patients supply both estimates")
    print("=" * 100)
    keep = [f for f in order if f in obs and 3 in obs[f]]
    wins = {f: [] for f in keep if f != INV}
    if INV in keep and len(keep) > 1:
        alive3 = dday > 3
        for _ in range(NBOOT):
            i = rng.integers(0, n, n)
            yb, axb, a3 = y[i], ax[i], alive3[i]
            if not (0 < yb.sum() < n):
                continue

            def ratio(f):
                v = preds[f][i]
                X0 = np.column_stack([np.ones(n), axb, v, v * axb])
                k = int(a3.sum())
                if k < 250 or not (0 < yb[a3].sum() < k):
                    return None
                Xa = np.column_stack([np.ones(k), axb[a3], v[a3], v[a3] * axb[a3]])
                try:
                    b0 = float(logit_fit(X0, yb)[3]); b1 = float(logit_fit(Xa, yb[a3])[3])
                except Exception:
                    return None
                if not (np.isfinite(b0) and np.isfinite(b1)) or abs(b0) < 1e-6:
                    return None
                return b1 / b0

            ri = ratio(INV)
            if ri is None:
                continue
            for f in wins:
                rf = ratio(f)
                if rf is not None:
                    wins[f].append(1.0 if ri > rf else 0.0)
        print(f"   {'visible flag (same patients)':>30}   P(invisible retains more at day 3)   resamples")
        for f in sorted(wins, key=lambda k: -np.mean(wins[k]) if wins[k] else 0):
            if len(wins[f]) >= 100:
                print(f"   {f:>30}   {100*float(np.mean(wins[f])):>32.0f}%   {len(wins[f]):>9,}")
            else:
                print(f"   {f:>30}   {'too few usable resamples':>32}   {len(wins[f]):>9,}")

    # ---- verdict -------------------------------------------------------------------------------------
    print("\n" + "=" * 100)
    print("VERDICT")
    print("=" * 100)
    win = [L for L in (0, 1, 2, 3)]
    inv_below = [L for L in win if L in null.get(INV, {}) and obs[INV][L] < null[INV][L][1]]
    vis_below = {f: [L for L in win if L in null.get(f, {}) and obs[f][L] < null[f][L][1]]
                 for f in usable if f in obs}
    any_vis = [f for f, v in vis_below.items() if len(v) >= 3]
    if INV not in null or not null[INV]:
        print("   NO VERDICT — the invisible measure's null was not estimable in this stratum.")
    elif inv_below:
        print(f"   Z2 FALSIFIED — the invisible measure falls below its own null inside the window at "
              f"{', '.join('day '+str(L) for L in inv_below)}.")
        print("   R408's window contrast is then cohort, not predictor, and must be withdrawn.")
    elif not any_vis:
        print("   Z2 FALSIFIED — no visible flag in this stratum falls below its null across the window,")
        print("   so there is nothing for the invisible measure to be contrasted against here.")
        print(f"   (per-flag landmarks below null: "
              f"{ {f: len(v) for f, v in vis_below.items()} })")
    else:
        print(f"   Z2 CONFIRMED — the invisible measure stays inside its null at days 0-3, while "
              f"{', '.join(any_vis)} falls below its own null across the window, in the SAME patients.")
    print("\n   This says nothing about burst suppression's own curve: every patient here has the flag, so")
    print("   its interaction is undefined in this stratum. R408's onset contrast remains confounded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
