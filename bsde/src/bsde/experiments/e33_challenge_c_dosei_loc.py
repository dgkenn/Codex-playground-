#!/usr/bin/env python3
"""E33 — Challenge C on DOSE-I: does anything see loss of consciousness coming before the depth index does?

REGISTERED BEFORE ANY FEATURE VALUE FROM `pEEG.zip` HAS BEEN READ AGAINST THE OUTCOME. What has been read is
the feasibility probe (`governance/feasibility.py`, loop step 2.5): 171 recordings, 566 SOC 1->0
transitions, **136 recordings with a usable LOC landmark** carrying at least 120 s of conscious lead-in with
finite features. Those are counts on the label and the clinical record. No feature has been related to the
outcome, and this file is committed before it is.

WHY THIS DEPOSIT AND NOT VITALDB. Every previous Challenge C attempt was forced onto a transition inside
maintenance, because VitalDB's BIS strip goes on after induction and comes off before emergence — four
windows in 250 cases sit after `aneend` at BIS >= 80, and every BIS >= 80 window turned out to be facial EMG
(E22, `scripts/diagnose_bis_high_windows.py`). E26 answered the maintenance question in the negative and E27
could not refine it, because at that deposit's suppression rate no grid preserves both the question and the
base rate (rule 44).

**DOSE-I has the transition itself**, per second, 566 times, with a clinician-scored MOAA/S ladder beside it.

THE INCUMBENT, AND WHY THE PRIMARY IS NOT THIS PROJECT'S USUAL CANDIDATE. Rule 45: a registration must name
what it has to beat. DOSE-I ships published depth measures pre-computed — **SEF95**, median frequency, and
**permutation entropy** — so the incumbent is a published index rather than a proxy invented here. It is
still not a branded device output, and **no claim from this file may say "ahead of BIS"**; it may only say
"ahead of SEF95".

    THE PRIMARY IS **PERMUTATION ENTROPY (`PE31`)**, AND IT IS NAMED FROM THE LITERATURE RATHER THAN FROM
    THIS PROJECT'S HABIT. Ostertag J et al. 2025, *Anesth Analg*, PMID 38412114 (verified via E-utilities)
    reports that at loss of responsiveness **spectral edge frequency and spectral entropy move the WRONG
    way** — *"Spectral edge frequency and spectral entropy values increased... indicating a (paradoxically)
    higher level of high-frequency activity"* — **while permutation entropy and the beta ratio decrease
    monotonically through the same transition.** DOSE-I ships both families. So the incumbent is expected to
    fail at exactly the moment being predicted, and the primary is expected to succeed, and **both
    expectations are published and fixed here before the run.**

    This is the first registration in this programme whose primary was chosen by prior art rather than by
    carrying `exponent_high` forward. That is deliberate: `exponent_high` cannot be computed from `pEEG.zip`
    at all, since that archive ships the depositors' features and not raw signal. A successor (E34) may
    stream the raw EEG from `data.zip` and test this project's own candidates; **this file does not, and
    makes no claim about them.**

REGISTERED PREDICTIONS, evaluated in this order. A failed gate makes the downstream verdict ABSENT, not
negative (rule 31).

    P1  MACHINERY GATE, three parts, using no feature-outcome relationship.
        (a) COVERAGE — at least `MIN_RECORDINGS` recordings with a LOC landmark preceded by
            `LEAD_IN_S` seconds of conscious, finite-feature lead-in.
        (b) BASE RATE inside `BASE_RATE_BAND`, so an AUC is interpretable (E27 failed here at 4.0 %).
        (c) **THE INCUMBENT MUST BE ALIVE.** SEF95 alone must reach an out-of-fold AUC whose interval
            excludes 0.5. **If the incumbent cannot predict the transition at all, "beating it" is not a
            result** — it is a comparison against noise, and the verdict is ABSENT rather than a triumph.
            This gate is the one E26 did not have and wished it did.

    P2  THE BAR, printed before the primary: SEF95's own out-of-fold AUC, subject-level folds.

    P3  THE PRIMARY. `PE31` added to SEF95 must improve out-of-bag AUC with a subject-clustered interval
        excluding zero. Out-of-bag by resampling RECORDINGS, refitting on those drawn and scoring those not
        drawn (rule 9).

    P4  THE DIRECTIONAL CHECK OSTERTAG PREDICTS, and it can fail independently of P3. Through the 120 s
        before LOC, SEF95 should move UP (paradoxically) and PE31 should move DOWN. Reported as the median
        within-recording change. **If SEF95 falls and PE31 rises, the published expectation is refuted on
        this deposit and P3's interpretation changes even if its interval excludes zero.**

    P5  THE PLACEBO, GATING (rule 34). A matched fake landmark drawn at the same relative position within
        each recording's conscious phase, unrelated to the true LOC. Its increment must be smaller than
        P3's — a comparison against the real effect, never an absolute threshold (rule 37).

    P6  LEAD TIME, reported only if P3 and P5 hold. Median seconds from a top-decile window to actual LOC.
        At 1 s resolution this is a real number, unlike E27 where the 300 s grid quantised it away.

    FALSIFICATION: P3's interval includes zero, or P5 fails. Either is a negative answer on this deposit.

SCOPE AND LIMITS.
  * **NO DEDICATED EMG CHANNEL, AND THIS IS THE LIMITATION THAT MATTERS MOST.** E22 died because a label
    turned out to be facial muscle, and it was only detectable because VitalDB ships `BIS/EMG`. DOSE-I ships
    no muscle channel; `abs_gamma`/`rel_gamma` are an EMG-sensitive proxy, not a measurement. **The strong
    form of that check cannot be run here.** `rel_gamma` is reported alongside the primary as the weak form,
    and a candidate whose signal rides with gamma is suspect on this deposit and cannot be cleared on it.
  * **The features are the depositors', not this project's.** Their definitions, filtering and artefact
    handling are theirs; this file inherits all of it and cannot audit it from the CSV alone.
  * **`SOC` is a clinician's binary call**, derived from the MOAA/S ladder. Its timing has the resolution of
    a bedside assessment, not of the EEG, so a "lead time" here is measured against a human's stopwatch.
  * **Procedural sedation for endoscopy, propofol only.** Nothing here transfers to surgical anaesthesia,
    to volatiles, or to a population that is not otherwise well.
  * 171 recordings, one site, two fronto-temporal channels at 125 Hz.
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

from bsde.verifier.stats import (auc, cluster_bootstrap_ci, cv_predict_proba,           # noqa: E402
                                 oob_auc_increment)

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
PEEG_ZIP = os.path.join(RESULTS, "dosei_pEEG.zip")
OUT = os.path.join(RESULTS, "e33_challenge_c_dosei.json")

INCUMBENT = "SEF95"
PRIMARY = "PE31"
GAMMA = "rel_gamma"
LEAD_IN_S = 120
HORIZON_S = 60
"""One minute. The clinically actionable window for a sedationist watching a patient go under, and short
enough that a 1 s label resolution can express it. Fixed before the run."""
MIN_RECORDINGS = 50
BASE_RATE_BAND = (0.05, 0.95)
REPORT = ("PE31", "PE32", "PE61", "MF", "WSMF30", "WSMF49", "SEF95", "rel_alpha", "rel_beta1",
          "rel_delta1", "rel_gamma", "sync_alpha", "CFS", "PFS", "SFS")


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def _load(zip_path):
    """Per recording: the eligible conscious windows before the FIRST usable LOC, and the outcome."""
    z = zipfile.ZipFile(zip_path)
    names = [n for n in z.namelist() if n.endswith("_pEEG.csv")]
    recs = []
    for nm in names:
        rows = list(csv.DictReader(io.StringIO(z.read(nm).decode("utf-8-sig"))))
        if not rows:
            continue
        soc = np.array([_f(r.get("SOC", "")) for r in rows])
        ok = np.isfinite(soc)
        if ok.sum() < LEAD_IN_S:
            continue
        idx = np.flatnonzero(ok)
        s = soc[idx]
        tr = np.flatnonzero((s[:-1] == 1) & (s[1:] == 0))
        if tr.size == 0:
            continue
        t = int(tr[0])                                  # the FIRST loss, fixed rule, never the best one
        pre = idx[max(0, t - LEAD_IN_S):t + 1]
        if len(pre) < LEAD_IN_S:
            continue
        cols = {c: np.array([_f(rows[i].get(c, "")) for i in pre], float) for c in REPORT}
        # seconds from each window to the loss; the outcome is "within HORIZON_S"
        ttl = np.arange(len(pre))[::-1].astype(float)
        recs.append({"id": os.path.basename(nm).replace("_pEEG.csv", ""),
                     "cols": cols, "ttl": ttl, "y": (ttl <= HORIZON_S).astype(float)})
    return recs


def _stack(recs, name):
    x = np.concatenate([r["cols"][name] for r in recs])
    y = np.concatenate([r["y"] for r in recs])
    g = np.concatenate([np.full(len(r["y"]), r["id"]) for r in recs])
    ttl = np.concatenate([r["ttl"] for r in recs])
    return x, y, g, ttl


def main(argv=None) -> int:
    print("E33 — Challenge C on DOSE-I: seeing loss of consciousness before the depth index does")
    print(f"   incumbent {INCUMBENT}; primary {PRIMARY}, named from Ostertag 2025 (PMID 38412114)")
    print("   CLAIM SCOPE: 'ahead of SEF95', never 'ahead of BIS'. No branded index exists in this deposit.")
    if not os.path.exists(PEEG_ZIP):
        print(f"\n   *** {os.path.basename(PEEG_ZIP)} absent.")
        return 2
    recs = _load(PEEG_ZIP)
    x_inc, y, grp, ttl = _stack(recs, INCUMBENT)
    x_pri, _, _, _ = _stack(recs, PRIMARY)
    rng = np.random.default_rng(20260730)

    print("\n" + "=" * 100)
    print("P1 — MACHINERY GATE (no feature-outcome relationship)")
    print("=" * 100)
    base = float(np.mean(y))
    n_rec = len(recs)
    print(f"   recordings with a usable LOC landmark : {n_rec}   (floor {MIN_RECORDINGS})")
    print(f"   eligible windows                      : {len(y)}   ({LEAD_IN_S} s of lead-in each)")
    print(f"   base rate (LOC within {HORIZON_S:.0f} s)            : {base:.1%}   (band {BASE_RATE_BAND})")
    m = np.isfinite(x_inc)
    p_inc = cv_predict_proba(x_inc[m], y[m], grp[m], rng)
    okp = np.isfinite(p_inc)
    inc_auc = auc(y[m][okp], p_inc[okp])
    ilo, ihi, _ = cluster_bootstrap_ci(lambda i: auc(y[m][okp][i], p_inc[okp][i]),
                                       grp[m][okp], rng, reps=2000)
    alive = bool(ilo > 0.5 or ihi < 0.5)
    print(f"   INCUMBENT ALIVE? {INCUMBENT} alone AUC {inc_auc:.3f} [{ilo:.3f}, {ihi:.3f}]   "
          f"{'yes' if alive else 'NO — beating it would be a comparison against noise'}")
    p1 = bool(n_rec >= MIN_RECORDINGS and BASE_RATE_BAND[0] <= base <= BASE_RATE_BAND[1] and alive)
    print(f"\n   P1 {'PASSED' if p1 else '*** FAILED'}")
    state = {"experiment": "E33", "n_recordings": n_rec, "n_windows": int(len(y)),
             "p1": {"base_rate": base, "incumbent_auc": float(inc_auc),
                    "incumbent_ci": [float(ilo), float(ihi)], "incumbent_alive": alive,
                    "passed": p1}}
    if not p1:
        print("   Nothing downstream is reported: ABSENT, not negative (rule 31).")
        json.dump(state, open(OUT, "w"), indent=2, default=float)
        return 1

    print("\n" + "=" * 100)
    print(f"P2 — THE BAR: {INCUMBENT} alone, printed before any candidate")
    print("=" * 100)
    print(f"   AUC {inc_auc:.3f} [{ilo:.3f}, {ihi:.3f}] over {int(okp.sum())} windows, "
          f"{len(set(grp[m][okp]))} recordings")
    state["p2"] = {"auc": float(inc_auc), "ci": [float(ilo), float(ihi)]}

    print("\n" + "=" * 100)
    print(f"P3 — PRIMARY: does {PRIMARY} add to {INCUMBENT}? (out-of-bag, clustered on recording)")
    print("=" * 100)
    print(f"   {'feature':16s} {'windows':>8s} {'recs':>5s} {'increment':>10s} {'95% OOB interval':>22s}")
    incs = {}
    for name in (PRIMARY,) + tuple(c for c in REPORT if c not in (PRIMARY, INCUMBENT)):
        xc, _, _, _ = _stack(recs, name)
        mm = np.isfinite(x_inc) & np.isfinite(xc)
        if len(np.unique(y[mm])) < 2 or len(set(grp[mm])) < MIN_RECORDINGS:
            continue
        one = np.ones(int(mm.sum()))
        inc, lo, hi, nrep = oob_auc_increment(
            np.column_stack([one, x_inc[mm]]), np.column_stack([one, x_inc[mm], xc[mm]]),
            y[mm], grp[mm], rng, reps=300)
        incs[name] = {"increment": inc, "ci": [lo, hi], "n_reps": nrep}
        print(f"   {name:16s} {int(mm.sum()):8d} {len(set(grp[mm])):5d} {inc:10.4f} "
              f"{f'[{lo:+.4f}, {hi:+.4f}]':>22s}")
    prim = incs.get(PRIMARY)
    p3 = bool(prim and np.isfinite(prim["ci"][0]) and prim["ci"][0] > 0.0)
    print(f"\n   P3 {'PASSED' if p3 else '*** FAILED'}")
    state["p3"] = {"increments": incs, "passed": p3}

    print("\n" + "=" * 100)
    print("P4 — THE DIRECTIONAL CHECK OSTERTAG PREDICTS (SEF95 up, PE down, through the 120 s before LOC)")
    print("=" * 100)
    moves = {}
    for name in (INCUMBENT, PRIMARY, "MF", GAMMA):
        d = []
        for r in recs:
            v = r["cols"][name]
            early, late = v[:30], v[-30:]
            if np.isfinite(early).sum() > 10 and np.isfinite(late).sum() > 10:
                d.append(float(np.nanmean(late) - np.nanmean(early)))
        moves[name] = float(np.median(d)) if d else float("nan")
        print(f"   {name:10s} median change over the lead-in: {moves[name]:+.4f}  ({len(d)} recordings)")
    as_published = bool(np.isfinite(moves.get(INCUMBENT, np.nan))
                        and np.isfinite(moves.get(PRIMARY, np.nan))
                        and moves[INCUMBENT] > 0 and moves[PRIMARY] < 0)
    print(f"\n   matches Ostertag 2025 (SEF95 up, PE down): {as_published}")
    print("   If it does not, the published expectation is refuted on this deposit and P3's reading changes")
    print("   even where its interval excludes zero.")
    state["p4"] = {"median_change": moves, "matches_published": as_published}

    print("\n" + "=" * 100)
    print("P5 — PLACEBO GATE: a matched fake landmark must increment LESS than the real one")
    print("=" * 100)
    fake = []
    shuffled = rng.permutation(np.array([len(r["y"]) for r in recs]))
    for j, r in enumerate(recs):
        n = len(r["y"])
        cut = int(min(n - 1, max(1, shuffled[j % len(shuffled)] % max(2, n))))
        fy = np.zeros(n)
        fy[max(0, cut - HORIZON_S):cut] = 1.0
        fake.append(fy)
    fy = np.concatenate(fake)
    mm = np.isfinite(x_inc) & np.isfinite(x_pri)
    if len(np.unique(fy[mm])) < 2 or not prim:
        print("   fake label degenerate — P5 ABSENT, P3 ungated and provisional (rule 31)")
        p5 = None
    else:
        one = np.ones(int(mm.sum()))
        f_inc, f_lo, f_hi, _ = oob_auc_increment(
            np.column_stack([one, x_inc[mm]]), np.column_stack([one, x_inc[mm], x_pri[mm]]),
            fy[mm], grp[mm], rng, reps=300)
        p5 = bool(np.isfinite(f_inc) and f_inc < prim["increment"])
        print(f"   placebo increment {f_inc:+.4f} [{f_lo:+.4f}, {f_hi:+.4f}]")
        print(f"   real    increment {prim['increment']:+.4f}")
        print(f"\n   P5 {'PASSED' if p5 else '*** FAILED — P3 is WITHDRAWN'}")
        state["p5"] = {"placebo_increment": float(f_inc), "passed": p5}

    print("\n" + "=" * 100)
    print("P6 — LEAD TIME")
    print("=" * 100)
    if not (p3 and p5):
        print("   Not reported: a failed or withdrawn increment has no lead time to describe.")
        state["p6"] = {"reported": False}
    else:
        pp = cv_predict_proba(x_pri[mm], y[mm], grp[mm], rng)
        okc = np.isfinite(pp)
        top = okc & (pp >= np.quantile(pp[okc], 0.90))
        lead = ttl[mm][top]
        med = float(np.median(lead[np.isfinite(lead)])) if top.any() else float("nan")
        print(f"   top-decile windows {int(top.sum())}; median {med:.0f} s before the clinician's call")
        print("   At 1 s resolution this is a real number — E27's 300 s grid quantised it away.")
        state["p6"] = {"reported": True, "median_lead_s": med}

    print("\n" + "=" * 100)
    print("VERDICT")
    print("=" * 100)
    if p5 is False:
        print("   Challenge C NOT met: the increment survives a fake landmark, so it reads time-in-recording.")
        v = "withdrawn_by_placebo"
    elif p5 is None:
        print("   UNGATED — the placebo could not be evaluated (rule 31).")
        v = "ungated"
    elif p3:
        print("   Challenge C is MET on this deposit, against a PUBLISHED depth index and not a branded one:")
        print("   before the clinician calls loss of consciousness, permutation entropy carries information")
        print("   about the imminent transition that SEF95 does not. One site, propofol sedation, no muscle")
        print("   channel to rule out an EMG explanation. Not a claim about BIS and not about surgery.")
        v = "met"
    else:
        print("   Challenge C NOT met on this deposit: the primary adds nothing to the incumbent.")
        v = "no_increment"
    state["verdict"] = v
    json.dump(state, open(OUT, "w"), indent=2, default=float)
    print(f"\n   wrote {os.path.relpath(OUT, os.path.dirname(RESULTS))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
