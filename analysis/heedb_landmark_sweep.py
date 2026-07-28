#!/usr/bin/env python3
"""R407 split the cohort once, at day 3. If withdrawal is doing the work the attenuation should be a CURVE,
and a matched null should show the curve is not just power loss.

WHY THIS EXISTS. R407 found that burst suppression's aetiology-dependence retains 37 % past a day-3 landmark
while the invisible intra-burst measure retains 93 %. Two objections are fair and neither was answered there:

  (O1) ONE LANDMARK IS ONE CHOICE. Day 3 was picked because most withdrawal happens inside it. A single split
       cannot distinguish a genuine time-structure from a lucky cut point.
  (O2) THE LANDMARK REMOVES PATIENTS AND EVENTS. Restricting to survivors shrinks n from 9,302 to 8,110 and
       drops the event rate. Interaction terms are the noisiest thing in a logistic model, so SOME attenuation
       is expected from power and prevalence alone, for every predictor, with no withdrawal involved.

This tests both. The sweep answers (O1); a size- and event-matched resampling null answers (O2), and the null
is the part that makes the result interpretable rather than suggestive.

------------------------------------------------------------------------------------------------------------
REGISTERED, before the data was looked at.

  Y1  SWEEP. For landmarks L in {0, 1, 2, 3, 5, 7, 10, 14} days, restrict to patients alive at day L and
      re-estimate the aetiology x predictor interaction on identical code. Report beta(L) / beta(full) — the
      retained fraction — for every visible flag and for the invisible measure.

  Y2  MATCHED NULL, and this is the decisive control. At each L, draw from the FULL cohort a subsample with
      the SAME n, the same 30-day death rate and the same anoxic fraction as the landmark cohort, and
      re-estimate. Repeat and take the median retained fraction. This is the attenuation attributable to
      power and prevalence with NO landmark applied.
        CONFIRMED IF burst suppression's observed curve falls clearly below its own matched null.
        FALSIFIED IF the observed curve sits inside the matched null's spread — which would mean R407's 37 %
        was a power artefact and the behavioural argument loses its timing evidence.

  Y3  CONTRAST. The prediction that separates the two accounts is about SHAPE, not level: a guideline-driven
      association should decay as the landmark moves past the withdrawal window and then flatten, while a
      biological one should track its matched null at every L. Report Spearman rho of (observed - null)
      against L for burst suppression and for the invisible measure.

WHAT A POSITIVE MEANS. That the timing structure in R407 is real and not a consequence of throwing away
patients. It still does not measure withdrawal — N14 records four failed attempts to build that variable — so
the argument remains indirect.
WHAT IT CANNOT MEAN. That the visible findings carry no biology. Attenuation of an INTERACTION is not
abolition of a main effect, and this script tests only the interaction.

HONEST LIMIT STATED UP FRONT. As L grows the estimand itself changes: "death by day 30 among those alive at
day L" is not the same quantity as "death by day 30". The matched null does not fix that, because the null
matches the marginal event rate but not the conditioning. The sweep is therefore evidence about shape, and the
shape is only interpretable against the invisible measure, which is subject to the identical conditioning.
"""
import csv, glob, io, os, sys
from collections import defaultdict
from datetime import datetime

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from icare_morph_replication import logit_fit
from heedb_bs_ascertainment import AETIOLOGY, norm
# The sandbox exports placeholder AWS_* env vars that shadow the real profile -- common/awsenv.py.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.awsenv import sanitize as _aws_sanitize; _aws_sanitize()

AP = "arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-credentialed-access-point"
OMOP_OLD = os.environ.get("OMOP_OUT", "/tmp/eeg_probe/heedb_omop")
OMOP_Q = os.environ.get("OMOP_QUANT", "/tmp/eeg_probe/heedb_omop_quant")
MORPH = os.environ.get("HEEDB_MORPH", "/tmp/eeg_probe/heedb_burst_morph.s*.csv")
NNULL = int(os.environ.get("NNULL", "150"))
LANDMARKS = [0, 1, 2, 3, 5, 7, 10, 14]
FLAGS = ["bs", "gpd", "lpd", "seizure", "gen slowing", "foc slowing"]


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

    rows = []
    for p in anox:
        if p not in when or p not in find:
            continue
        d = death.get(p)
        days = (d - when[p]).days if d is not None else None
        if days is not None and days < -1:
            continue
        rows.append((p, days, 1.0 if anox[p] else 0.0, ab.get(p)))
    n = len(rows)
    y = np.array([0.0 if r[1] is None else (1.0 if r[1] <= 30 else 0.0) for r in rows])
    ax = np.array([r[2] for r in rows])
    dday = np.array([1e9 if r[1] is None else float(r[1]) for r in rows])
    has_ab = np.array([r[3] is not None for r in rows])
    abv = np.array([0.0 if r[3] is None else r[3] for r in rows])
    preds = {f: np.array([1.0 if find[r[0]][f] else 0.0 for r in rows]) for f in FLAGS}
    preds["intra-burst 8-30 Hz"] = abv
    avail = {f: np.ones(n, bool) for f in FLAGS}
    avail["intra-burst 8-30 Hz"] = has_ab

    print(f"cohort {n:,}   30-day death {100*y.mean():.1f}%   anoxic {100*ax.mean():.1f}%"
          f"   with the invisible measure {int(has_ab.sum()):,}")

    def inter(v, m):
        k = int(m.sum())
        if k < 250 or not (0 < y[m].sum() < k):
            return None
        X = np.column_stack([np.ones(k), ax[m], v[m], v[m] * ax[m]])
        try:
            return float(logit_fit(X, y[m])[3])
        except Exception:
            return None

    # ---- baseline: the full-cohort interaction, per predictor -------------------------------------
    base = {}
    for f, v in preds.items():
        base[f] = inter(v, avail[f])

    # ---- Y1 sweep + Y2 matched null ---------------------------------------------------------------
    obs = defaultdict(dict)
    null = defaultdict(dict)
    sizes = {}
    for L in LANDMARKS:
        alive = (dday > L)
        for f, v in preds.items():
            m = alive & avail[f]
            sizes[(f, L)] = (int(m.sum()), float(y[m].mean()) if m.sum() else float("nan"))
            b = inter(v, m)
            if b is not None and base[f] and abs(base[f]) > 1e-9:
                obs[f][L] = b / base[f]
            # matched null: same n, same event rate, same anoxic fraction, NO landmark
            pool = avail[f]
            tgt_n = int(m.sum())
            if tgt_n < 250 or tgt_n >= int(pool.sum()):
                continue
            cells = {}
            for yy in (0.0, 1.0):
                for aa in (0.0, 1.0):
                    cells[(yy, aa)] = np.flatnonzero(pool & (y == yy) & (ax == aa))
            want = {k: int(round(float(((y[m] == k[0]) & (ax[m] == k[1])).sum())))
                    for k in cells}
            if any(want[k] > len(cells[k]) for k in cells):
                continue
            vals = []
            for _ in range(NNULL):
                idx = np.concatenate([rng.choice(cells[k], want[k], replace=False)
                                      for k in cells if want[k] > 0])
                mm = np.zeros(n, bool); mm[idx] = True
                b2 = inter(v, mm)
                if b2 is not None and base[f] and abs(base[f]) > 1e-9:
                    vals.append(b2 / base[f])
            if len(vals) >= 30:
                null[f][L] = (float(np.median(vals)),
                              float(np.percentile(vals, 5)), float(np.percentile(vals, 95)))

    order = ["bs", "intra-burst 8-30 Hz"] + [f for f in FLAGS if f != "bs"]
    print("\n" + "=" * 108)
    print("Y1 / Y2  RETAINED FRACTION BY LANDMARK DAY — observed against a size/event/aetiology-matched null")
    print("=" * 108)
    for f in order:
        if not obs[f]:
            continue
        tag = "INVISIBLE" if f.startswith("intra") else "visible"
        print(f"\n  {f}   ({tag})   full-cohort interaction {base[f]:+.3f}")
        print(f"    {'landmark':>9} {'n':>7} {'death%':>7} {'observed':>10} {'matched null (5-95%)':>26} {'gap':>8}")
        for L in LANDMARKS:
            if L not in obs[f]:
                continue
            k, er = sizes[(f, L)]
            if L in null[f]:
                nm, lo, hi = null[f][L]
                gap = obs[f][L] - nm
                s = f"{100*nm:>7.0f}% [{100*lo:>4.0f}%,{100*hi:>4.0f}%]"
                below = "  BELOW" if obs[f][L] < lo else ""
                print(f"    {'day '+str(L):>9} {k:>7,} {100*er:>6.1f}% {100*obs[f][L]:>9.0f}% "
                      f"{s:>26} {100*gap:>+7.0f}%{below}")
            else:
                print(f"    {'day '+str(L):>9} {k:>7,} {100*er:>6.1f}% {100*obs[f][L]:>9.0f}% "
                      f"{'(null not estimable)':>26}")

    # ---- Y3 shape contrast -------------------------------------------------------------------------
    print("\n" + "=" * 108)
    print("Y3  SHAPE: does the observed curve fall away from its own matched null as the landmark moves?")
    print("=" * 108)

    def rho(f):
        L = [x for x in LANDMARKS if x in obs[f] and x in null[f]]
        if len(L) < 4:
            return None
        g = [obs[f][x] - null[f][x][0] for x in L]
        rl = np.argsort(np.argsort(L)).astype(float)
        rg = np.argsort(np.argsort(g)).astype(float)
        rl -= rl.mean(); rg -= rg.mean()
        d = float(np.sqrt((rl ** 2).sum() * (rg ** 2).sum()))
        return (float((rl * rg).sum() / d) if d > 0 else None), len(L)

    summary = {}
    for f in order:
        r = rho(f)
        if r and r[0] is not None:
            summary[f] = r[0]
            print(f"   {f:>22}   rho(observed - null, landmark day) = {r[0]:+.2f}   over {r[1]} landmarks")

    print("\n" + "=" * 108)
    print("VERDICT")
    print("=" * 108)
    bs_below = [L for L in LANDMARKS
                if L in obs["bs"] and L in null["bs"] and obs["bs"][L] < null["bs"][L][1]]
    inv = "intra-burst 8-30 Hz"
    inv_below = [L for L in LANDMARKS
                 if L in obs[inv] and L in null[inv] and obs[inv][L] < null[inv][L][1]]
    if not (obs["bs"] and null["bs"]):
        print("   NO VERDICT — the null was not estimable for burst suppression; nothing is claimed.")
    else:
        print(f"   burst suppression falls below its matched null at {len(bs_below)} of "
              f"{len([L for L in LANDMARKS if L in null['bs']])} landmarks: "
              f"{', '.join('day '+str(L) for L in bs_below) or 'none'}")
        print(f"   the invisible measure falls below its own null at {len(inv_below)} of "
              f"{len([L for L in LANDMARKS if L in null[inv]])}: "
              f"{', '.join('day '+str(L) for L in inv_below) or 'none'}")
        if bs_below and not inv_below:
            print("   Y2 CONFIRMED — burst suppression attenuates beyond what power loss explains, and the")
            print("   invisible measure does not. That is the pattern the behavioural account predicts.")
        elif bs_below and inv_below:
            print("   Y2 PARTIAL — both fall below their nulls, so excess attenuation is not specific to the")
            print("   visible finding. Compare the magnitudes, and do not claim specificity.")
        else:
            print("   Y2 FALSIFIED — burst suppression stays inside its matched null. R407's 37 % is then")
            print("   consistent with power loss, and the timing evidence for the behavioural account fails.")
    print("\n   The estimand changes as the landmark moves (see the docstring). Withdrawal is unmeasured.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
