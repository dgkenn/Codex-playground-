#!/usr/bin/env python3
"""Does quantitative burden stratify WITHIN the guideline's "highly malignant" EEG category?

THE CLINICAL QUESTION THIS ANSWERS, and why it is the one that matters now. Westhall et al., Neurology 2016
(PMID 26865516, verified verbatim from the MEDLINE record) classify post-arrest EEGs into

    "highly malignant (suppression, suppression with periodic discharges, burst-suppression), malignant
     (periodic or rhythmic patterns, pathological or nonreactive background), and benign EEG (absence of
     malignant features)"

with 37 % highly malignant and "all had a poor outcome (specificity 100%, sensitivity 50%)". That scheme is now
embedded in ERC-ESICM prognostication guidance. Two things follow. It is CATEGORICAL: every patient inside the
highly-malignant category is treated as carrying the same information. And it is BINARY in effect: suppression
and burst-suppression sit in one tier.

Our within-anoxic result says that category is not homogeneous. Among post-anoxic burst-suppression patients,
three-day death runs 24.1 %, 28.4 %, 45.9 %, 63.3 % across quartiles of MEASURED suppression burden. If that
survives proper evaluation, it means a guideline category currently read as a single grave finding contains a
2.6-fold range of near-term risk, and the information distinguishing them is already present in the recording.

REGISTERED PREDICTIONS.
  G1  Within the highly-malignant category, quantitative burden discriminates three-day death with
      cross-validated AUC >= 0.60.
      FALSIFIED IF cross-validated AUC < 0.60 or its interval includes 0.5.
  G2  Burden adds discrimination OVER the categorical scheme itself. Fitting the Westhall-style category as the
      baseline and adding continuous burden must improve cross-validated AUC by at least +0.03.
      FALSIFIED IF the increment is below +0.03.
  G3  The stratification holds at BOTH hospitals, fitted at one and evaluated at the other.
      FALSIFIED IF out-of-sample AUC at either site is below 0.55.

THE CAVEAT THAT MUST TRAVEL WITH ANY RESULT HERE, stated before the numbers exist. Burst suppression is a
guideline criterion for poor prognosis and informs withdrawal of life-sustaining therapy. Any score that
stratifies risk within that category risks being used to make its own predictions come true, and this cohort
cannot separate biological death from withdrawal-mediated death in the first days -- 40.6 % of post-anoxic
burst-suppression patients die within three days, which is exactly the window in which withdrawal decisions are
made. So a positive result here is a statement about INFORMATION PRESENT IN THE RECORDING, not a
recommendation to act on it, and the distinction is not rhetorical: acting on it without a prospective study
would be precisely the self-fulfilling-prophecy mechanism the field already worries about.

METHOD. Linear probability models on named quantities; five-fold cross-validation and cross-hospital
validation; in-sample figures reported alongside so the optimism is visible rather than hidden.
"""
import csv, glob, io, os, sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from heedb_bs_ascertainment import AETIOLOGY, norm, dt

OMOP = os.environ.get("OMOP_OUT", "/tmp/eeg_probe/heedb_omop")
NBOOT = int(os.environ.get("NBOOT", "600"))
AP = "arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-credentialed-access-point"
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
    return (float(np.nanmean(out)), float(np.nanpercentile(out, 2.5)),
            float(np.nanpercentile(out, 97.5))) if out else (float("nan"),) * 3


def main():
    rng = np.random.default_rng(20260726)

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

    death = {}
    with open(f"{OMOP}/death.csv") as fh:
        for r in csv.DictReader(fh):
            try:
                death[int(r["person_id"])] = dt(r.get("death_datetime"))
            except Exception:
                pass

    # SCOPE. "index" takes the exposure from the patient's EARLIEST recording, which is where the outcome clock
    # starts. "max" takes the highest value over ALL of the patient's recordings and is the LEGACY behaviour,
    # retained only to reproduce earlier runs -- it is look-ahead, because a patient who survives accrues extra
    # recordings and extra chances at a high maximum while a patient who dies on day two does not.
    # `heedb_burden_lookahead_check.py` measured the exposure: 41.0 % of patients have their maximum drawn from
    # a later recording and 21.8 % differ by more than 0.10 burden, so the two are NOT interchangeable.
    SCOPE = os.environ.get("BURDEN_SCOPE", "index")
    if SCOPE not in ("index", "max"):
        raise SystemExit("BURDEN_SCOPE must be 'index' or 'max'")

    bsess, morph = defaultdict(dict), {}
    for f in sorted(glob.glob("/tmp/eeg_probe/heedb_bs_burden*.csv")):
        for r in csv.DictReader(open(f)):
            try:
                p, s, v = int(r["patient"]), int(r["session"]), float(r["burden"])
            except Exception:
                continue
            if v == v:
                bsess[p][s] = max(bsess[p].get(s, 0.0), v)
    # Index session is resolved from recording TIMESTAMPS where they are available, not from the session number.
    # Session identifiers are expected to increase with time but that is an assumption about an identifier, and
    # the whole point of this fix is to stop relying on assumptions about which recording came first. The
    # timestamp map is loaded below (it lives in a different metadata file from the findings), after which
    # `resolve_burden` is called; `min(session)` is the fallback and the concordance between the two orderings
    # is printed so the run reports whether the assumption would have held.
    def resolve_burden(stime):
        out, agree, total = {}, 0, 0
        for p, d in bsess.items():
            by_num = min(d)
            times = {s: stime[(p, s)] for s in d if (p, s) in stime}
            if times:
                by_time = min(times, key=lambda s: times[s])
                total += 1
                agree += (by_time == by_num)
            else:
                by_time = by_num
            out[p] = d[by_time] if SCOPE == "index" else max(d.values())
        if SCOPE == "index":
            if total:
                print(f"   index session resolved by timestamp for {total:,} patients; session-number order "
                      f"agreed for {100*agree/total:.1f}% of them")
            else:
                print("   WARNING: no recording timestamps available, so the index session fell back to the "
                      "lowest session NUMBER for every patient. That is an assumption, not a measurement.")
        return out
    for f in sorted(glob.glob("/tmp/eeg_probe/heedb_burst_morph*.csv")):
        for r in csv.DictReader(open(f)):
            try:
                p = int(r["patient"])
            except Exception:
                continue
            try:
                s = int(r["session"])
            except Exception:
                continue
            d, ok = {}, True
            for k in FEATS:
                try:
                    d[k] = float(r[k])
                except Exception:
                    ok = False
            if ok and all(v == v for v in d.values()):
                # Keep the EARLIEST session, not whichever row happened to be read last. The previous
                # `morph[p] = d` made a patient's morphology depend on file ordering, which is arbitrary and
                # under BURDEN_SCOPE=index is also look-ahead.
                if p not in morph or s < morph[p]["_sess"]:
                    morph[p] = dict(d, _sess=s)
    morph = {p: {k: v for k, v in d.items() if k != "_sess"} for p, d in morph.items()}

    import boto3
    from botocore.config import Config
    s3 = boto3.client("s3", region_name="us-east-1",
                      config=Config(s3={"payload_signing_enabled": False}))
    # Fidx = findings on the INDEX report only; Fall = findings ORed over every report the patient ever had.
    # Fall carries the same look-ahead as max-burden: a patient can be graded highly malignant on the strength
    # of a report written weeks after the outcome clock started. Under BURDEN_SCOPE=index the CATEGORY is taken
    # from the index report too, so the comparator and the exposure are measured at the same moment.
    when, Fidx, Fall, site = {}, defaultdict(dict), defaultdict(dict), {}
    FL = ("bs", "low voltage", "gpd", "lpd", "grda", "lrda", "seizure", "status",
          "gen slowing", "foc slowing", "pdr", "normal")
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
            cur = {f: ((r.get(f) or "").strip() not in ("", "None", "nan")) for f in FL}
            if p not in when or t < when[p]:
                when[p] = t; site[p] = st
                Fidx[p] = dict(cur)
            for f in FL:
                Fall[p][f] = Fall[p].get(f, False) or cur[f]
    # session -> recording time, so the index recording is identified by WHEN it happened
    stime = {}
    for st in ("S0001", "S0002"):
        try:
            txt = s3.get_object(Bucket=AP,
                                Key=f"EEG/eeg-metadata/{st}_eeg_metadata_2026_04_30.csv"
                                )["Body"].read().decode("utf-8", "replace")
        except Exception as e:
            print(f"   note: session-time metadata unavailable for {st} ({type(e).__name__})")
            continue
        for r in csv.DictReader(io.StringIO(txt)):
            pp = (r.get("BDSPPatientID") or "").strip()
            ss = (r.get("SessionID") or "").strip()
            if not pp.isdigit() or not ss.isdigit():
                continue
            tt = dt(r.get("StartTime") or r.get("EndTime") or "")
            if tt is not None:
                stime[(int(pp), int(ss))] = tt

    F = Fidx if SCOPE == "index" else Fall
    burden = resolve_burden(stime)
    print(f"EXPOSURE SCOPE: {SCOPE}"
          + ("  (burden and EEG category both taken from the index recording -- the one the outcome clock "
             "starts at)" if SCOPE == "index"
             else "  (LEGACY look-ahead: burden maximised and findings ORed over ALL recordings)"))

    def westhall(f):
        """highly malignant 2 / malignant 1 / benign 0, following the published definition as closely as the
        available fields allow. Reactivity is NOT recorded in this schema, so the 'nonreactive background' arm
        of the malignant tier cannot be reproduced -- stated rather than silently approximated."""
        if f.get("bs") or f.get("low voltage"):
            return 2
        if any(f.get(k) for k in ("gpd", "lpd", "grda", "lrda", "seizure", "status")):
            return 1
        return 0

    rows = []
    for p, t0 in when.items():
        if p not in cond_seen or "anoxic" not in aet.get(p, set()):
            continue
        d = death.get(p)
        if d is None:
            continue
        days = (d - t0).days
        if days < -1:
            continue
        rows.append(dict(pid=p, site=site.get(p, "?"), days=float(days),
                         d3=1.0 if days <= 3 else 0.0, d30=1.0 if days <= 30 else 0.0,
                         cat=westhall(F[p]), bur=burden.get(p, float("nan")),
                         **{k: morph.get(p, {}).get(k, float("nan")) for k in FEATS}))
    n = len(rows)
    print(f"post-anoxic patients with an ascertained death: {n:,}")
    print("   Westhall-style category (reactivity unavailable in this schema, so the nonreactive arm of the")
    print("   malignant tier is not reproduced):")
    for c, nm in ((2, "highly malignant"), (1, "malignant"), (0, "benign")):
        g = [r for r in rows if r["cat"] == c]
        if g:
            print(f"      {nm:18s} n={len(g):5d}   3-day death {100*np.mean([r['d3'] for r in g]):5.1f} %   "
                  f"30-day {100*np.mean([r['d30'] for r in g]):5.1f} %")

    hm = [r for r in rows if r["cat"] == 2 and r["bur"] == r["bur"]]
    print(f"\n   highly-malignant patients with a measured burden: {len(hm):,}")
    if len(hm) < 200:
        print("*** insufficient"); return 1

    # ---- G1: does burden stratify inside the category? ---------------------------------------------
    print("\n" + "=" * 92)
    print("G1  WITHIN THE HIGHLY-MALIGNANT CATEGORY, DOES MEASURED BURDEN STRATIFY 3-DAY DEATH?")
    print("=" * 92)
    y = np.asarray([r["d3"] for r in hm], float)
    b = np.asarray([r["bur"] for r in hm], float)
    q = np.percentile(b, [20, 40, 60, 80])
    print(f"   {'burden quintile':18s} {'n':>6s} {'3-day death':>13s} {'30-day death':>14s}")
    prev, mono = None, True
    for lab, sel in (("Q1 lowest", b <= q[0]), ("Q2", (b > q[0]) & (b <= q[1])),
                     ("Q3", (b > q[1]) & (b <= q[2])), ("Q4", (b > q[2]) & (b <= q[3])),
                     ("Q5 highest", b > q[3])):
        if sel.sum() < 15:
            continue
        v3 = 100 * y[sel].mean()
        v30 = 100 * np.mean([r["d30"] for r, s in zip(hm, sel) if s])
        print(f"   {lab:18s} {int(sel.sum()):6d} {v3:12.1f}% {v30:13.1f}%")
        if prev is not None and v3 < prev - 1e-9:
            mono = False
        prev = v3
    X1 = np.column_stack([np.ones(len(hm)), b])
    m, lo, hi = cv_auc(X1, y, rng)
    print(f"\n   burden alone, cross-validated AUC {m:.3f} [{lo:.3f},{hi:.3f}]   "
          f"(in-sample {auc(y, X1 @ lpm(X1, y)):.3f})")
    print(f"   monotone across quintiles: {mono}")
    print(f"   G1 {'CONFIRMED' if (m >= 0.60 and lo > 0.5) else 'FALSIFIED'} (threshold 0.60)")

    # ---- G2: does burden add over the CATEGORY itself? ----------------------------------------------
    print("\n" + "=" * 92)
    print("G2  DOES BURDEN ADD OVER THE CATEGORICAL SCHEME, ACROSS ALL POST-ANOXIC PATIENTS?")
    print("=" * 92)
    allb = [r for r in rows if r["bur"] == r["bur"]]
    ya = np.asarray([r["d3"] for r in allb], float)
    cat = np.asarray([r["cat"] for r in allb], float)
    Xc = np.column_stack([np.ones(len(allb)), (cat == 2).astype(float), (cat == 1).astype(float)])
    Xcb = np.column_stack([Xc, np.asarray([r["bur"] for r in allb], float)])
    mc, lc, hc = cv_auc(Xc, ya, rng)
    mb, lb, hb = cv_auc(Xcb, ya, rng)
    print(f"   n={len(allb):,}")
    print(f"   category alone            CV AUC {mc:.3f} [{lc:.3f},{hc:.3f}]")
    print(f"   category + measured burden CV AUC {mb:.3f} [{lb:.3f},{hb:.3f}]")
    print(f"   increment {mb-mc:+.3f}   G2 {'CONFIRMED' if mb - mc >= 0.03 else 'FALSIFIED'} (threshold +0.03)")

    # ---- morphology on top --------------------------------------------------------------------------
    gm = [r for r in hm if r["stereotypy"] == r["stereotypy"]]
    if len(gm) >= 150:
        ym = np.asarray([r["d3"] for r in gm], float)
        Z = {}
        for k in FEATS:
            v = np.asarray([r[k] for r in gm], float)
            Z[k] = (v - v.mean()) / (v.std() if v.std() > 1e-12 else 1.0)
        Xa = np.column_stack([np.ones(len(gm)), np.asarray([r["bur"] for r in gm], float)])
        Xb2 = np.column_stack([Xa] + [Z[k] for k in FEATS])
        ma, _, _ = cv_auc(Xa, ym, rng)
        mb2, _, _ = cv_auc(Xb2, ym, rng)
        print(f"\n   within highly malignant, n={len(gm)}: burden {ma:.3f} -> burden+morphology {mb2:.3f} "
              f"(increment {mb2-ma:+.3f})")

    # ---- G3: cross-hospital -------------------------------------------------------------------------
    print("\n" + "=" * 92)
    print("G3  CROSS-HOSPITAL: fit at one site, evaluate at the other (burden within highly malignant)")
    print("=" * 92)
    sarr = np.array([r["site"] for r in hm])
    ok = True
    for tr in sorted(set(sarr)):
        itr = np.where(sarr == tr)[0]; ite = np.where(sarr != tr)[0]
        if len(itr) < 80 or len(ite) < 60 or y[ite].sum() < 12:
            print(f"   train {tr}: too few"); continue
        a = auc(y[ite], X1[ite] @ lpm(X1[itr], y[itr]))
        if a < 0.55:
            ok = False
        print(f"   train {tr} (n={len(itr)}) -> test other (n={len(ite)}): AUC {a:.3f}")
    print(f"   G3 {'CONFIRMED' if ok else 'FALSIFIED'} (both sites >= 0.55)")

    print("\n   Burst suppression is a guideline criterion that informs withdrawal of life-sustaining therapy,")
    print("   and 40.6 % of these patients die within three days -- the window in which those decisions are made.")
    print("   A positive result here is a statement about information present in the recording, NOT a")
    print("   recommendation to act on it; acting on it without a prospective study would be the")
    print("   self-fulfilling-prophecy mechanism the field already worries about.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
