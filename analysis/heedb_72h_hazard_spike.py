#!/usr/bin/env python3
"""If guideline-timed withdrawal is real, it should leave a fingerprint in the CLOCK: a hazard spike at 72 h,
specific to anoxic burst-suppressed patients. Biology has no reason to know what hour it is.

WHERE THIS COMES FROM. R409 stripped R407 back to one surviving claim: burst suppression's aetiology
interaction collapses across the withdrawal window (84 %, 77 %, 63 %, 37 % at days 0-3; below its matched null
at all eight landmarks; sign-crossing by day 5). Two readings remain and the landmark cannot separate them:

  (A) BIOLOGY. Hypoxic-ischaemic mortality is genuinely front-loaded, so an anoxia-specific association is
      expressed early and is spent by day 5. Nothing about clinician behaviour is required.
  (B) BEHAVIOUR. ERC-ESICM tells clinicians not to prognosticate before **72 hours** after arrest, and names
      burst suppression as a malignant pattern. Withdrawal decisions therefore cluster just after that mark.

**These differ in a way neither the landmark nor the matched null can see.** (A) predicts a SMOOTH,
monotonically decaying hazard — injury severity does not consult a calendar. (B) predicts a LOCAL BUMP at a
specific hour that a guideline names, present in the cell the guideline addresses and absent in the others.
A round-numbered discontinuity is a signature of a decision rule, not of pathophysiology.

------------------------------------------------------------------------------------------------------------
REGISTERED, before the data was looked at.

  V1  DISCRETE HAZARD, not raw counts. For each of four cells — anoxic x burst-suppression-flag — compute
      h[d] = deaths on day d / patients still alive at the start of day d, for d = 0..14. Raw counts fall
      with depletion and would manufacture any shape.

  V2  PRIMARY. The bump statistic is the LOCAL EXCESS: mean h over days 2-4 divided by mean h over days 5-7.
      An adjacent-window ratio is used rather than an absolute rate so that cells with different overall
      mortality are comparable, and so that a globally steeper decay does not read as a bump.
        CONFIRMED IF the anoxic + burst-suppression cell's excess exceeds ALL THREE other cells, with a
        bootstrap interval on each pairwise difference that excludes 1.
        FALSIFIED IF the excess is not highest in that cell, or if its intervals include 1 — which would
        mean there is no guideline-timed discontinuity and reading (A) is preferred.

  V3  NEGATIVE CONTROL, on the same cells. Days 0-1 mortality reflects the arrest itself and precedes any
      prognostication, so a behavioural account predicts NO anoxic-BS-specific excess there. If the day-0-1
      contrast looks like the day-2-4 contrast, the statistic is tracking case mix and V2 means nothing.

  V4  PLACEBO CUT. Repeat V2 with the bump window moved to days 6-8 over days 9-11. A guideline account
      predicts nothing there. If a "bump" appears at an arbitrary cut too, the statistic is not specific.
      **V4 GATES V2.** No positive verdict may be announced for V2 while the placebo is also firing; the
      first version of this script printed "V2 CONFIRMED" with V4 lit, which is error-catalogue rule 31.

  V5  LOCALITY, added after the first run because V2 and V4 disagreed and the disagreement exposed a real
      defect in V2's design. **An adjacent-window ratio does not test locality at all** — a cell that simply
      decays more steeply scores high on it with no discontinuity anywhere, which is what happened. A spike
      is a LOCAL phenomenon, so the right statistic is the second difference: h[d] divided by the mean of
      h[d-1] and h[d+1]. Under a decision rule the peak sits at the guideline's day; under front-loaded
      biology every day scores ~1 because a monotone decay has no interior peak.
      **This is a descriptive amendment, not a confirmatory test.** It was specified after seeing V1's
      hazard rows and is reported as such.

THE ANCHORING LIMITATION, STATED BEFORE THE RESULT. Death day is measured from the FIRST EEG, not from the
arrest, because HEEDB carries no arrest time (`visit_disposition` is 100 % empty and covers 715 patients —
R409). The arrest-to-EEG lag is unmeasured and variable, which SMEARS any true 72 h spike across days. So
**only a positive is informative here**: a spike that survives smearing is strong evidence, while its absence
is equally consistent with a real spike that the smearing has washed out. This asymmetry is not a
post-hoc excuse; it is why the test is registered with a one-sided interpretation.
"""
import csv, io, os, sys
from collections import defaultdict
from datetime import datetime

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.awsenv import sanitize as _aws_sanitize; _aws_sanitize()
from heedb_bs_ascertainment import AETIOLOGY, norm

AP = "arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-credentialed-access-point"
OMOP_OLD = os.environ.get("OMOP_OUT", "/tmp/eeg_probe/heedb_omop")
OMOP_Q = os.environ.get("OMOP_QUANT", "/tmp/eeg_probe/heedb_omop_quant")
NBOOT = int(os.environ.get("NBOOT", "2000"))
DMAX = 15
BUMP, REF = (2, 3, 4), (5, 6, 7)
PBUMP, PREF = (6, 7, 8), (9, 10, 11)


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
    bs, when = {}, {}
    for st in ("S0001", "S0002"):
        txt = s3.get_object(Bucket=AP,
                            Key=f"EEG/HEEDB_Metadata/{st}_EEG__reports_findings.csv"
                            )["Body"].read().decode("utf-8", "replace")
        for r in csv.DictReader(io.StringIO(txt)):
            p = (r.get("BDSPPatientID") or "").strip()
            if not p.isdigit():
                continue
            p = int(p)
            bs[p] = bs.get(p, False) or ((r.get("bs") or "").strip() not in ("", "None", "nan"))
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
    return bs, when, death, anox


def hazard(dd, idx):
    """Discrete hazard h[d] over days 0..DMAX-1 for the patients in idx. dd = death day, 1e9 = no death."""
    h = np.full(DMAX, np.nan)
    d = dd[idx]
    for t in range(DMAX):
        at_risk = int((d >= t).sum())
        if at_risk >= 25:
            h[t] = float((d == t).sum()) / at_risk
    return h


def excess(h, bump, ref):
    a = np.nanmean(h[list(bump)]) if not np.all(np.isnan(h[list(bump)])) else np.nan
    b = np.nanmean(h[list(ref)]) if not np.all(np.isnan(h[list(ref)])) else np.nan
    if not np.isfinite(a) or not np.isfinite(b) or b <= 0:
        return np.nan
    return a / b


def main():
    rng = np.random.default_rng(20260728)
    bs, when, death, anox = load()

    rows = []
    for p in anox:
        if p not in when or p not in bs:
            continue
        d = death.get(p)
        days = (d - when[p]).days if d is not None else None
        if days is not None and days < -1:
            continue
        rows.append((1.0 if anox[p] else 0.0, 1.0 if bs[p] else 0.0,
                     1e9 if days is None else float(max(days, 0))))
    n = len(rows)
    A = np.array([r[0] for r in rows])
    B = np.array([r[1] for r in rows])
    dd = np.array([r[2] for r in rows])
    cells = {
        "anoxic + BS": (A == 1) & (B == 1),
        "anoxic, no BS": (A == 1) & (B == 0),
        "non-anoxic + BS": (A == 0) & (B == 1),
        "non-anoxic, no BS": (A == 0) & (B == 0),
    }
    print(f"cohort {n:,}    deaths within {DMAX} days {int((dd < DMAX).sum()):,}")
    for k, m in cells.items():
        print(f"   {k:>20}  n = {int(m.sum()):>6,}   died within {DMAX} d: "
              f"{100*float((dd[m] < DMAX).mean()):>5.1f}%")

    # ---- V1 -------------------------------------------------------------------------------------
    print("\n" + "=" * 100)
    print("V1  DISCRETE DAILY HAZARD (deaths on day d / alive at the start of day d), in %")
    print("=" * 100)
    print(f"   {'cell':>20} " + " ".join(f"{'d'+str(t):>5}" for t in range(DMAX)))
    H = {}
    for k, m in cells.items():
        H[k] = hazard(dd, np.flatnonzero(m))
        print(f"   {k:>20} " + " ".join(
            (f"{100*v:>5.1f}" if np.isfinite(v) else "    .") for v in H[k]))

    # ---- V2 / V4 --------------------------------------------------------------------------------
    def report(bump, ref, title, primary):
        print("\n" + "=" * 100)
        print(title)
        print("=" * 100)
        pt = {k: excess(H[k], bump, ref) for k in cells}
        boots = {k: [] for k in cells}
        for _ in range(NBOOT):
            i = rng.integers(0, n, n)
            for k in cells:
                idx = np.flatnonzero(cells[k][i])
                if len(idx) < 100:
                    boots[k].append(np.nan); continue
                boots[k].append(excess(hazard(dd[i], idx), bump, ref))
        print(f"   {'cell':>20} {'excess':>9} {'bootstrap 2.5-97.5%':>24}")
        for k in cells:
            v = np.array(boots[k], float); v = v[np.isfinite(v)]
            ci = (f"[{np.percentile(v,2.5):.2f}, {np.percentile(v,97.5):.2f}]"
                  if len(v) >= NBOOT // 4 else "(not estimable)")
            print(f"   {k:>20} {pt[k]:>9.2f} {ci:>24}")
        tgt = "anoxic + BS"
        print(f"\n   pairwise: {tgt} excess divided by each other cell's")
        beats = []
        for k in cells:
            if k == tgt:
                continue
            v = np.array([a / b if (np.isfinite(a) and np.isfinite(b) and b > 0) else np.nan
                          for a, b in zip(boots[tgt], boots[k])], float)
            v = v[np.isfinite(v)]
            if len(v) < NBOOT // 4:
                print(f"      vs {k:>20}: not estimable"); beats.append(False); continue
            lo, hi = np.percentile(v, [2.5, 97.5])
            ok = lo > 1.0
            print(f"      vs {k:>20}: {pt[tgt]/pt[k] if np.isfinite(pt[k]) and pt[k]>0 else float('nan'):>6.2f}x "
                  f"[{lo:.2f}, {hi:.2f}]{'   EXCLUDES 1' if ok else ''}")
            beats.append(ok)
        return pt, all(beats), boots

    v2, v2_beats, _ = report(BUMP, REF,
                             "V2  PRIMARY — hazard on days 2-4 relative to days 5-7 (the 72 h mark)", True)
    v4, v4_beats, v4_boots = report(PBUMP, PREF,
                                    "V4  PLACEBO CUT — days 6-8 over days 9-11, where no guideline acts",
                                    False)

    # V4 gates V2. The placebo fires if the target cell's own excess at an arbitrary cut also excludes 1.
    pv = np.array([x for x in v4_boots["anoxic + BS"] if np.isfinite(x)], float)
    placebo_fires = len(pv) >= NBOOT // 4 and float(np.percentile(pv, 2.5)) > 1.0
    print("\n" + "=" * 100)
    print("V2 VERDICT, GATED BY V4")
    print("=" * 100)
    if not v2_beats:
        print("   V2 FALSIFIED — the anoxic burst-suppressed cell does not exceed all three others.")
    elif placebo_fires:
        print(f"   V2 NOT INTERPRETABLE — its criterion passed, but the PLACEBO CUT also fires in the same")
        print(f"   cell ({v4['anoxic + BS']:.2f}, 2.5th pct {np.percentile(pv, 2.5):.2f} > 1). A statistic that")
        print("   finds a 'bump' at an arbitrary day is measuring how steeply the hazard decays, not when.")
        print("   No claim about guideline timing may be made from V2.")
    else:
        print("   V2 CONFIRMED and the placebo is silent — a discontinuity specific to the guideline's day.")

    # ---- V5 locality ------------------------------------------------------------------------------
    print("\n" + "=" * 100)
    print("V5  LOCALITY (descriptive amendment) — h[d] / mean(h[d-1], h[d+1]); a spike scores > 1 at ONE day")
    print("=" * 100)

    def local(h):
        out = np.full(DMAX, np.nan)
        for t in range(1, DMAX - 1):
            nb = np.nanmean([h[t - 1], h[t + 1]])
            if np.isfinite(h[t]) and np.isfinite(nb) and nb > 0:
                out[t] = h[t] / nb
        return out

    print(f"   {'cell':>20} " + " ".join(f"{'d'+str(t):>5}" for t in range(1, DMAX - 1)))
    for k in cells:
        L = local(H[k])
        print(f"   {k:>20} " + " ".join(
            (f"{v:>5.2f}" if np.isfinite(v) else "    .") for v in L[1:DMAX - 1]))
    LT = local(H["anoxic + BS"])
    fin = [(t, LT[t]) for t in range(1, DMAX - 1) if np.isfinite(LT[t])]
    if fin:
        t_max, v_max = max(fin, key=lambda x: x[1])
        boots = []
        for _ in range(NBOOT):
            i = rng.integers(0, n, n)
            idx = np.flatnonzero(cells["anoxic + BS"][i])
            if len(idx) < 100:
                continue
            lv = local(hazard(dd[i], idx))
            if np.isfinite(lv[t_max]):
                boots.append(lv[t_max])
        b = np.array(boots, float); b = b[np.isfinite(b)]
        ci = (f"[{np.percentile(b,2.5):.2f}, {np.percentile(b,97.5):.2f}]"
              if len(b) >= NBOOT // 4 else "(not estimable)")
        print(f"\n   anoxic + BS: largest local excess is {v_max:.2f} at day {t_max}, bootstrap {ci}")
        print(f"   a monotone decay scores ~1 at every interior day and has no peak; a decision rule puts")
        print(f"   the peak at the guideline's day (day 2-4 here, given the arrest-to-EEG lag).")

    # ---- V3 -------------------------------------------------------------------------------------
    print("\n" + "=" * 100)
    print("V3  NEGATIVE CONTROL — days 0-1, before any prognostication is permitted")
    print("=" * 100)
    print(f"   {'cell':>20} {'h(d0-1), %':>12}")
    for k in cells:
        v = np.nanmean(H[k][[0, 1]])
        print(f"   {k:>20} {100*v:>11.2f}%")
    print("\n   If the day-0-1 ordering matches the day-2-4 ordering, the bump statistic is tracking case")
    print("   mix rather than timing, and V2 must not be read as evidence about behaviour.")

    print("\n   ANCHORING: day 0 is the first EEG, not the arrest. The unmeasured arrest-to-EEG lag smears")
    print("   any true 72 h spike, so a null here is weak evidence and a positive is strong.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
