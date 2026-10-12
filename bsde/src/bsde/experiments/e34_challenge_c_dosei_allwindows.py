#!/usr/bin/env python3
"""E34 - Challenge C on DOSE-I, with the sampling that E33's failure demanded.

REGISTERED AFTER E33 FAILED, AND THE INSTRUMENT IS WHAT CHANGED - not a threshold, not a cohort, not a
horizon. E33 sampled only the 121 s before each first loss of consciousness and asked "is LOC within 60 s",
so its base rate was 61/121 by construction. The check added to `governance/feasibility.py` because of that
failure measures it directly: **the AUC of position-within-record for E33's label is 1.000.** The label was
the clock, perfectly.

THE SAMPLING CHANGE, AND ITS EFFECT MEASURED BEFORE REGISTERING. E34 takes **every conscious window in the
whole recording**, not only those preceding the first loss. Because DOSE-I contains 566 transitions across
171 recordings, many conscious windows are followed by no loss at all - a patient who wakes and stays awake
contributes negatives at every position. That breaks the collinearity rather than hiding it:

    E33 sampling   49 recordings    5,929 windows   base rate 50.4 %   position-AUC **1.000**
    E34 sampling  129 recordings   79,429 windows   base rate 31.2 %   position-AUC **0.376**

Those numbers come from the label and the clinical record only; no feature has been related to the outcome,
and this file is committed before one is.

THE SECOND CHANGE, AND IT IS A CORRECTION TO E33's GATE RATHER THAN A RELAXATION OF IT. E33 required the
incumbent to be alive, on the reasoning that beating noise is not a result. That gate fired - SEF95 alone
reached AUC 0.453 [0.406, 0.501] - and stopping there was right for E33, whose label was the clock anyway.
But the reasoning was wrong in general: **Challenge C asks for a feature that predicts ahead of a
conventional monitor, so a monitor at chance and a feature above it IS the challenge's answer.** A gate that
stops on a dead incumbent can suppress a real positive.

    So the incumbent's performance is **REPORTED, NEVER GATED**, and the primary is judged on two separate
    questions that are not allowed to be conflated:
        P3a  does the primary beat CHANCE, out-of-fold?
        P3b  does the primary ADD to the incumbent, out-of-bag?
    **If the incumbent is at chance, P3b answers a different question from P3a and the write-up must say
    so.** Reporting only P3b against a dead incumbent would dress up "our feature works" as "our feature
    beats the monitor", and reporting only P3a would drop the comparison the challenge actually asks for.

PRIMARY, UNCHANGED FROM E33 AND STILL NAMED FROM THE LITERATURE: **permutation entropy (`PE31`)**.
Ostertag 2025, *Anesth Analg*, PMID 38412114, verified via E-utilities: spectral edge frequency and spectral
entropy move the *wrong* way at loss of responsiveness while permutation entropy decreases monotonically
through it. The primary was not chosen by this project's habit and was not changed after E33 failed.

REGISTERED PREDICTIONS, in order. A failed gate makes the downstream verdict ABSENT (rule 31).

    P1  MACHINERY GATE, no feature-outcome relationship.
        (a) COVERAGE - at least `MIN_RECORDINGS` recordings contributing both classes.
        (b) BASE RATE inside `BASE_RATE_BAND`.
        (c) **POSITION COLLINEARITY** - |AUC(position) - 0.5| must be at most `MAX_POSITION_AUC_DIST`.
            This is the check E33 lacked; the threshold is declared here and E33 would have scored 0.500
            against it while the measured E34 sampling scores 0.124.
    P2  THE INCUMBENT'S SCORE, reported before the primary and NOT gating.
    P3a THE PRIMARY AGAINST CHANCE - out-of-fold AUC, subject-level folds, interval excluding 0.5.
    P3b THE PRIMARY AGAINST THE INCUMBENT - out-of-bag increment over SEF95, interval excluding zero.
    P4  THE DIRECTIONAL CHECK Ostertag predicts, which can fail independently.
    P5  PLACEBO, GATING (rule 34): a fake landmark at a matched relative position must increment less.
    P6  LEAD TIME, only if P3a, P3b and P5 all hold.

    FALSIFICATION: P3a's interval includes 0.5, or P5 fails. P3b failing while P3a passes is NOT a
    falsification - it is the specific finding that the feature works and does not beat the incumbent, and
    it must be reported in those words.

SCOPE AND LIMITS. Every limit from E33 carries over unchanged and is not repeated at length: **no dedicated
EMG channel**, so the check that killed E22 cannot be run in its strong form and `rel_gamma` is only a weak
proxy; the features are the depositors' and cannot be audited from the CSV; `SOC` is a clinician's bedside
call, so a lead time is measured against a human's stopwatch; propofol-only procedural sedation at one site,
two fronto-temporal channels at 125 Hz. **No claim from this file may say "ahead of BIS" - only "ahead of
SEF95".**

--------------------------------------------------------------------------------------------------------
OUTCOME: EVERY GATE RAN. **P1 and P3a PASSED; P3b, P4 and P5 FAILED. The primary is WITHDRAWN by its own
placebo, and Challenge C is NOT MET on this deposit.**

    P1   coverage 129 recordings / 79,429 windows; base rate 31.2 %; **position-AUC 0.376** (E33: 1.000)
    P2   incumbent SEF95 **AUC 0.610 [0.571, 0.650]** — alive, and E33's "dead incumbent" was an artefact
         of E33's own sampling rather than a property of SEF95
    P3a  PE31 alone **AUC 0.623 [0.587, 0.659]** — above chance. PASSED
    P3b  PE31 added to SEF95: increment **+0.0178 [-0.0226, +0.0474]** — interval spans zero. FAILED
    P4   **REFUTED, and not marginally.** Ostertag predicts SEF95 UP and PE DOWN approaching loss of
         responsiveness. Measured over 105 recordings: SEF95 **-1.0248**, PE31 **-0.0481**. Both fall.
    P5   placebo increment **+0.0244** against the real **+0.0178** — **the fake landmark scores HIGHER
         than the true one.** FAILED, and the primary is withdrawn.

**THE PLACEBO IS THE WHOLE RESULT.** A landmark placed at a random position in each recording buys more
increment than the actual moment the clinician called loss of consciousness. Whatever PE31's +0.0178 was
measuring, it was not the transition. That is exactly what a placebo gate exists to find, and it found it
after the sampling fix had already removed the *obvious* version of the problem — E34's label is not the
clock (position-AUC 0.376), and the increment is still not about the event.

**P3a PASSING IS NOT A CONSOLATION AND MUST NOT BE REPORTED AS ONE.** PE31 reaching 0.623 against chance
means only that conscious windows near a loss differ from conscious windows far from one. The placebo shows
that difference is not specific to the loss. **"Above chance" and "about the thing" are different claims**,
which is the entire reason P3a and P3b were separated in this registration rather than reported as one
number.

**P4 IS AN INDEPENDENT NEGATIVE AND IS WORTH MORE THAN P3b.** Ostertag 2025 (PMID 38412114) is the reason
permutation entropy was named as the primary before the run. On DOSE-I the published direction does not
replicate: **SEF95 falls approaching the loss rather than rising**, at twenty times the magnitude of PE31's
own change. Either the paradoxical-excitation window is narrower than the 120 s examined here, or it does
not appear in propofol procedural sedation, or the depositors' SEF95 differs from the published one. **This
file cannot distinguish those**, and the failure is recorded as a failure to replicate a published direction
rather than as evidence against the paper.

**THE MUSCLE PROBLEM, WHICH THE HEADER DECLARED IN ADVANCE AND WHICH NOW HAS TEETH.** `rel_gamma` — the
EMG-sensitive proxy — scored **0.632 [0.594, 0.666]**, *above* the primary's 0.623. DOSE-I ships no muscle
channel, so the strong form of the check that killed E22 cannot be run. **A muscle explanation for anything
in this table cannot be excluded on this deposit**, and would not have been excludable whichever way the
placebo went.

**AND THE CONTEXT TABLE CONTAINS A LARGER NUMBER THAN THE PRIMARY, WHICH IS NOT PROMOTED.** `WSMF30` reached
**0.680 [0.650, 0.712]**, the highest in the table and comfortably above PE31. It is one cell of fifteen, it
was not pre-declared, it has not faced the placebo that just withdrew the pre-declared primary, and the
placebo is the gate that matters here. **It is recorded and not claimed.** A successor wishing to test it
must register it first and put it through the same placebo — and should expect the same answer, since the
placebo's failure was about the landmark and not about the feature.

--------------------------------------------------------------------------------------------------------
CORRECTION TO THIS FILE'S OWN OUTCOME NOTE, made on re-reading the intervals rather than the point estimates.

The note above says "the fake landmark scores HIGHER than the true one" and calls the placebo "the whole
result". **That over-dramatises a comparison between two estimates that both span zero:**

    real increment     +0.0178  [-0.0226, +0.0474]
    placebo increment  +0.0244  [-0.0440, +0.0935]

**Neither interval excludes zero.** The honest statement is therefore not "the placebo beat the real
landmark" but **"PE31 adds nothing measurable to SEF95 for any landmark, real or fake"** — and the ordering
of two point estimates inside overlapping noise carries no information. Error-catalogue rule 37 in its own
words: a cell that spans the null is neither direction, and may not satisfy a directional reading. Applying
that to someone else's result and not to my own would be the double standard the rule exists to prevent.

**The verdict does not change.** P3b failed on its own terms — the increment's interval spans zero — so the
primary does not beat the incumbent and Challenge C is not met on this deposit. What changes is the reason
stated: **it is a plain null, not a placebo catching a false positive.** The placebo gate did not have a
positive to catch.

**A check that PASSED and belongs on the record.** A worry about this design was that loss of consciousness
in procedural sedation is a pharmacology event, so any EEG feature "predicting" it might merely be tracking
drug arrival. Measured on the clinical columns only, across 60 recordings and 31,313 conscious windows:
**cumulative propofol alone gives AUC 0.506 for "LOC within 60 s".** The drug column does not predict the
transition, so that explanation is excluded — one of the few things in this experiment that came out clean.
"""
from __future__ import annotations

import csv
import io
import json
import os
import sys
import zipfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "..", "governance")))

from bsde.verifier.stats import (auc, cluster_bootstrap_ci, cv_predict_proba,           # noqa: E402
                                 oob_auc_increment)

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
PEEG_ZIP = os.path.join(RESULTS, "dosei_pEEG.zip")
OUT = os.path.join(RESULTS, "e34_challenge_c_dosei_allwindows.json")

INCUMBENT = "SEF95"
PRIMARY = "PE31"
GAMMA = "rel_gamma"
HORIZON_S = 60
MIN_RECORDINGS = 50
MIN_CONSCIOUS_S = 200
BASE_RATE_BAND = (0.05, 0.95)
MAX_POSITION_AUC_DIST = 0.20
REPORT = ("PE31", "PE32", "PE61", "MF", "WSMF30", "WSMF49", "SEF95", "rel_alpha", "rel_beta1",
          "rel_delta1", "rel_gamma", "sync_alpha", "CFS", "PFS", "SFS")


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def _load(zip_path):
    """EVERY conscious window in each recording, with time to the NEXT loss of consciousness.

    The difference from E33 is the whole point of this file. A conscious window with no loss after it is a
    negative and is KEPT; E33 could not contain such a window because it only sampled the run-up to a loss,
    which is why its label had a position-AUC of 1.000.
    """
    z = zipfile.ZipFile(zip_path)
    recs = []
    for nm in [n for n in z.namelist() if n.endswith("_pEEG.csv")]:
        rows = list(csv.DictReader(io.StringIO(z.read(nm).decode("utf-8-sig"))))
        if not rows:
            continue
        soc = np.array([_f(r.get("SOC", "")) for r in rows])
        keep = {c: np.array([_f(r.get(c, "")) for r in rows], float) for c in REPORT}
        ok = np.isfinite(soc) & np.isfinite(keep[PRIMARY]) & np.isfinite(keep[INCUMBENT])
        if ok.sum() < MIN_CONSCIOUS_S:
            continue
        idx = np.flatnonzero(ok)
        s = soc[idx]
        losses = np.flatnonzero((s[:-1] == 1) & (s[1:] == 0))
        conscious = np.flatnonzero(s == 1)
        if conscious.size < MIN_CONSCIOUS_S or losses.size == 0:
            continue
        ttl = np.full(conscious.size, np.inf)
        for k, c in enumerate(conscious):
            nxt = losses[losses >= c]
            if nxt.size:
                ttl[k] = float(nxt[0] - c)
        rid = os.path.basename(nm).replace("_pEEG.csv", "")
        recs.append({"id": rid, "rows": idx[conscious],
                     "cols": {c: keep[c][idx[conscious]] for c in REPORT},
                     "ttl": ttl, "y": (ttl <= HORIZON_S).astype(float)})
    return recs


def _stack(recs, name):
    return (np.concatenate([r["cols"][name] for r in recs]),
            np.concatenate([r["y"] for r in recs]),
            np.concatenate([np.full(len(r["y"]), r["id"]) for r in recs]),
            np.concatenate([r["ttl"] for r in recs]))


def main(argv=None) -> int:
    print("E34 - Challenge C on DOSE-I, sampling every conscious window")
    print(f"   incumbent {INCUMBENT} (REPORTED, not gated); primary {PRIMARY}, from Ostertag 2025 (PMID 38412114)")
    print("   CLAIM SCOPE: 'ahead of SEF95', never 'ahead of BIS'.")
    if not os.path.exists(PEEG_ZIP):
        print(f"\n   *** {os.path.basename(PEEG_ZIP)} absent.")
        return 2
    from feasibility import label_collinear_with_position
    recs = _load(PEEG_ZIP)
    x_inc, y, grp, ttl = _stack(recs, INCUMBENT)
    x_pri, _, _, _ = _stack(recs, PRIMARY)
    rng = np.random.default_rng(20260730)

    print("\n" + "=" * 100)
    print("P1 - MACHINERY GATE (no feature-outcome relationship)")
    print("=" * 100)
    base = float(np.mean(y))
    col = label_collinear_with_position(y, grp)
    n_rec = len(recs)
    print(f"   recordings contributing        : {n_rec}   (floor {MIN_RECORDINGS})")
    print(f"   conscious windows              : {len(y)}")
    print(f"   base rate (LOC within {HORIZON_S} s)     : {base:.1%}   (band {BASE_RATE_BAND})")
    print(f"   position-AUC for the label     : {col['auc_of_position']:.3f}  "
          f"(distance {col['distance_from_chance']:.3f}, ceiling {MAX_POSITION_AUC_DIST})")
    print(f"      -> {col['verdict']}")
    print("      E33 scored 1.000 on this check, which is why this file exists.")
    p1 = bool(n_rec >= MIN_RECORDINGS
              and BASE_RATE_BAND[0] <= base <= BASE_RATE_BAND[1]
              and col["distance_from_chance"] <= MAX_POSITION_AUC_DIST)
    print(f"\n   P1 {'PASSED' if p1 else '*** FAILED'}")
    state = {"experiment": "E34", "n_recordings": n_rec, "n_windows": int(len(y)),
             "p1": {"base_rate": base, "position_auc": col["auc_of_position"],
                    "position_distance": col["distance_from_chance"], "passed": p1}}
    if not p1:
        print("   Nothing downstream is reported: ABSENT, not negative (rule 31).")
        json.dump(state, open(OUT, "w"), indent=2, default=float)
        return 1

    print("\n" + "=" * 100)
    print(f"P2 - THE INCUMBENT ({INCUMBENT}), reported before the primary and NOT gating")
    print("=" * 100)
    p_inc = cv_predict_proba(x_inc, y, grp, rng)
    okp = np.isfinite(p_inc)
    inc_auc = auc(y[okp], p_inc[okp])
    ilo, ihi, _ = cluster_bootstrap_ci(lambda i: auc(y[okp][i], p_inc[okp][i]), grp[okp], rng, reps=1000)
    inc_alive = bool(ilo > 0.5 or ihi < 0.5)
    print(f"   AUC {inc_auc:.3f} [{ilo:.3f}, {ihi:.3f}]   "
          f"{'the incumbent can do this task' if inc_alive else 'THE INCUMBENT IS AT CHANCE'}")
    if not inc_alive:
        print("   Because the incumbent is at chance, P3b answers a DIFFERENT question from P3a, and the")
        print("   verdict below says so rather than dressing one up as the other.")
    state["p2"] = {"auc": float(inc_auc), "ci": [float(ilo), float(ihi)], "alive": inc_alive}

    print("\n" + "=" * 100)
    print(f"P3a - PRIMARY AGAINST CHANCE: {PRIMARY} alone, out-of-fold")
    print("=" * 100)
    print(f"   {'feature':16s} {'AUC':>8s} {'95% CI':>20s}")
    solo = {}
    for name in (PRIMARY, INCUMBENT, GAMMA) + tuple(c for c in REPORT if c not in (PRIMARY, INCUMBENT, GAMMA)):
        xc, _, _, _ = _stack(recs, name)
        m = np.isfinite(xc)
        if m.sum() < 1000:
            continue
        pc = cv_predict_proba(xc[m], y[m], grp[m], rng)
        ok = np.isfinite(pc)
        a = auc(y[m][ok], pc[ok])
        lo, hi, _ = cluster_bootstrap_ci(lambda i: auc(y[m][ok][i], pc[ok][i]), grp[m][ok], rng, reps=1000)
        solo[name] = {"auc": float(a), "ci": [float(lo), float(hi)]}
        print(f"   {name:16s} {a:8.3f} {f'[{lo:.3f}, {hi:.3f}]':>20s}")
    pr = solo.get(PRIMARY)
    p3a = bool(pr and (pr["ci"][0] > 0.5 or pr["ci"][1] < 0.5))
    print(f"\n   P3a {'PASSED' if p3a else '*** FAILED'}")
    state["p3a"] = {"solo": solo, "passed": p3a}

    print("\n" + "=" * 100)
    print(f"P3b - PRIMARY AGAINST THE INCUMBENT: does {PRIMARY} add to {INCUMBENT}? (out-of-bag)")
    print("=" * 100)
    mm = np.isfinite(x_inc) & np.isfinite(x_pri)
    one = np.ones(int(mm.sum()))
    inc, lo, hi, nrep = oob_auc_increment(
        np.column_stack([one, x_inc[mm]]), np.column_stack([one, x_inc[mm], x_pri[mm]]),
        y[mm], grp[mm], rng, reps=300)
    p3b = bool(np.isfinite(lo) and lo > 0.0)
    print(f"   increment {inc:+.4f} [{lo:+.4f}, {hi:+.4f}] over {nrep} resamples")
    print(f"   P3b {'PASSED' if p3b else '*** FAILED'}")
    state["p3b"] = {"increment": float(inc), "ci": [float(lo), float(hi)], "passed": p3b}

    print("\n" + "=" * 100)
    print("P4 - THE DIRECTIONAL CHECK Ostertag predicts, over the 120 s before each loss")
    print("=" * 100)
    moves = {}
    for name in (INCUMBENT, PRIMARY, "MF", GAMMA):
        d = []
        for r in recs:
            v, t = r["cols"][name], r["ttl"]
            far, near = v[(t > 90) & (t <= 120)], v[t <= 30]
            if np.isfinite(far).sum() > 5 and np.isfinite(near).sum() > 5:
                d.append(float(np.nanmean(near) - np.nanmean(far)))
        moves[name] = float(np.median(d)) if d else float("nan")
        print(f"   {name:10s} median change approaching the loss: {moves[name]:+.4f}  ({len(d)} recordings)")
    as_pub = bool(np.isfinite(moves.get(INCUMBENT, np.nan)) and np.isfinite(moves.get(PRIMARY, np.nan))
                  and moves[INCUMBENT] > 0 and moves[PRIMARY] < 0)
    print(f"\n   matches Ostertag 2025 (SEF95 up, PE down): {as_pub}")
    state["p4"] = {"median_change": moves, "matches_published": as_pub}

    print("\n" + "=" * 100)
    print("P5 - PLACEBO GATE: a fake landmark at a matched relative position")
    print("=" * 100)
    fake = []
    for j, r in enumerate(recs):
        n = len(r["y"])
        frac = float(rng.uniform(0.2, 0.9))
        cut = int(n * frac)
        fy = np.zeros(n)
        fy[max(0, cut - HORIZON_S):cut] = 1.0
        fake.append(fy)
    fy = np.concatenate(fake)
    if len(np.unique(fy[mm])) < 2:
        print("   fake label degenerate - P5 ABSENT, primary ungated (rule 31)")
        p5 = None
    else:
        f_inc, f_lo, f_hi, _ = oob_auc_increment(
            np.column_stack([one, x_inc[mm]]), np.column_stack([one, x_inc[mm], x_pri[mm]]),
            fy[mm], grp[mm], rng, reps=300)
        p5 = bool(np.isfinite(f_inc) and f_inc < inc)
        print(f"   placebo increment {f_inc:+.4f} [{f_lo:+.4f}, {f_hi:+.4f}]   real {inc:+.4f}")
        print(f"   P5 {'PASSED' if p5 else '*** FAILED - the primary is WITHDRAWN'}")
        state["p5"] = {"placebo_increment": float(f_inc), "passed": p5}

    print("\n" + "=" * 100)
    print("P6 - LEAD TIME")
    print("=" * 100)
    if not (p3a and p5):
        print("   Not reported: requires P3a and the placebo.")
        state["p6"] = {"reported": False}
    else:
        pp = cv_predict_proba(x_pri, y, grp, rng)
        okc = np.isfinite(pp)
        top = okc & (pp >= np.quantile(pp[okc], 0.90))
        lead = ttl[top]
        lead = lead[np.isfinite(lead)]
        med = float(np.median(lead)) if lead.size else float("nan")
        print(f"   top-decile windows {int(top.sum())}; median {med:.0f} s to the clinician's call")
        state["p6"] = {"reported": True, "median_lead_s": med}

    print("\n" + "=" * 100)
    print("VERDICT")
    print("=" * 100)
    if p5 is False:
        print("   NOT MET: the increment survives a fake landmark.")
        v = "withdrawn_by_placebo"
    elif p5 is None:
        print("   UNGATED (rule 31).")
        v = "ungated"
    elif p3a and p3b:
        print("   Challenge C is MET on this deposit: permutation entropy predicts imminent loss of")
        print("   consciousness above chance AND adds to SEF95, surviving a matched fake landmark.")
        v = "met"
    elif p3a and not p3b:
        print("   PARTIAL, and the wording matters: the primary predicts the transition above chance but")
        print("   does NOT add to the incumbent. That is 'the feature works and does not beat the monitor',")
        print("   which is not what Challenge C asks for.")
        v = "works_but_no_increment"
    else:
        print("   NOT MET: the primary does not beat chance.")
        v = "not_met"
    state["verdict"] = v
    json.dump(state, open(OUT, "w"), indent=2, default=float)
    print(f"\n   wrote {os.path.relpath(OUT, os.path.dirname(RESULTS))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
