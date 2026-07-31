#!/usr/bin/env python3
"""E42 — does the TEMPORAL STRUCTURE of alpha carry what its MAGNITUDE does not?

REGISTERED BEFORE `eegmmidb_rest_v2.*` FINISHES EXTRACTING. No value of either new candidate has been read
against any label.

**THIS IS A SECOND LOOK AT THIS COHORT AND SAYS SO.** E41 could open with "no candidate-label relationship
in this deposit has ever been observed" and mean it. That is no longer true: E41 scored fourteen candidates
against the imagery label and reported the full table. E42 adds two more candidates to the same cohort and
the same label, so **its p-values must be read against an accumulated search of sixteen, not two**, and the
multiplicity pass below uses the full sixteen rather than the new pair. Reporting a nominal p on the new
marker alone would be the garden of forking paths with a registration stapled to it.

WHY THESE TWO CANDIDATES, AND WHY NOW. E41's finding was that the incumbent — `relative_alpha_power`, a
deliberately weakened proxy for Blankertz 2010 — scored **rho = +0.2018 [+0.0050, +0.3857]** and beat all
fourteen candidates, none of which survived multiplicity. The refinement worth trying is therefore not a
fifteenth spectral summary but **a different property of the same rhythm**, and the literature names one:

    Ruiz-Rizzo et al., *Eur J Neurosci* 2021, **PMID 34618375**, verified through NCBI E-utilities and read
    in full (rules 25, 39): *"alpha power alone (magnitude) at rest was not associated with flexibility.
    However, we found that the participants' ability to manipulate VWM representations was correlated with
    alpha LRTC."*

    Thul et al., *NeuroImage* 2018, **PMID 29885482**: LRTC in beta amplitude rises under
    sevoflurane-induced unconsciousness; beta LRTC combined with alpha amplitude classifies state above
    80 %.

**THE DIRECTION IS NOT DECLARED, AND THAT IS A LIMITATION RATHER THAN A CHOICE.** PMID 34618375's abstract
states that the ability *"was correlated with alpha LRTC"* and **does not give the sign**. Rule 42: a
quotation supports only what it literally says. Inventing a direction and attributing it to that paper is
exactly the over-reading E31/E32 committed with Gugino 2001. So the primary is **two-sided**, which costs
power and is the honest price of not having the sign. If the full text supplies it, a successor may declare
it — this file may not.

`icoh_alpha` is included because E39's first-named deficit was that `wpli_alpha` was the only phase measure
in the registry. It is **not** the primary here and carries no directional prediction from Challenge B's
literature; it is in the reported table and the multiplicity family, nothing more.

REGISTERED BEFORE ANY VALUE IS READ. Failing branch written first throughout.

  G1  COVERAGE AND CEILING. At least `MIN_SUBJECTS` subjects with both a v2 resting row and a label, and
      E38's reliability interval must still exclude zero. The ceiling is **0.5402** and bounds everything.

  G2  **THE REDUNDANCY GATE, and it is the one that matters.** The whole claim is that alpha's temporal
      structure carries what its magnitude does not. So if `lrtc_alpha` correlates with
      `relative_alpha_power` across subjects above `MAX_REDUNDANCY` in absolute value, **the claim is
      refuted before any label is consulted** and the primary is not reported. This is the failure
      condition the candidate was registered with, promoted to a gate. Error-catalogue rule 28: this
      project has three times predicted two measurements would differ and found them redundant, and the
      cheap check is to look before designing on it.

  P1  THE INCUMBENT, reprinted from the same rows so the comparison is like-for-like:
      `relative_alpha_power` vs imagery AUC. E41 measured +0.2018 on the v1 table; a materially different
      value here means the re-extraction changed something and the comparison to E41 is void.

  P2  THE PRIMARY. `lrtc_alpha` vs imagery AUC, **two-sided**, interval excluding zero AND |rho| exceeding
      the incumbent's. Both conditions, because a marker that ties the incumbent has not refined anything.

  P3  PLACEBO, gating (rule 34): the same analysis against EXECUTED-movement decoding. The imagery
      association must exceed the executed one. NOT INFORMATIVE if P2 spans zero (rule 48).

  P4  MULTIPLICITY over the **full sixteen-candidate family**, not the new pair. Westfall-Young max-T with
      the label permuted across subjects.

  P5  REPORTED CONTEXT: the full table, and `lrtc_alpha`'s correlation with `critical_slowing_ar1` — the
      candidate's second registered failure condition, since both summarise an amplitude envelope.

VERDICT RULE, written before the run and stating the failing case first.

    NOT INTERPRETABLE   G1 failed.
    REFUTED BY REDUNDANCY  G2 failed: LRTC is a restatement of alpha power in this cohort, so the premise
                        of the refinement is false here regardless of any label.
    UNDERPOWERED NULL   P2 spans zero and |rho| < 0.272 — E41's minimum detectable effect, unchanged
                        because the cohort is unchanged. **Not a negative.**
    NOT MET             P2 excludes zero but does not beat the incumbent, or the placebo reaches it.
    REFINED             P2 excludes zero, beats the incumbent, and beats its placebo. Permitted sentence:
                        *"alpha LRTC correlates rho = X with motor-imagery ability, exceeding alpha power's
                        +0.2018, against a label whose reliability bounds any predictor at 0.54"* — with
                        the sixteen-candidate adjusted p beside it, always.

SCOPE, INHERITED AND UNCHANGED. Not a disorders-of-consciousness result. Healthy adults; motor imagery is
command-following that produces no movement, which is the right form and not the right population.
"""

from __future__ import annotations

import csv
import glob
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from bsde.verifier.stats import cluster_bootstrap_ci, spearman                          # noqa: E402
from bsde.verifier.multiplicity import westfall_young_maxt                              # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
REST_V2 = os.path.join(RESULTS, "eegmmidb_rest_v2.*.csv")
LABEL = os.path.join(RESULTS, "eegmmidb_bci.csv")
EXEC_LABEL = os.path.join(RESULTS, "eegmmidb_bci_executed.csv")
RELIABILITY = os.path.join(RESULTS, "e38_bci_label_reliability.json")
OUT = os.path.join(RESULTS, "e42_lrtc_refined_marker.json")

PRIMARY = "lrtc_alpha"
INCUMBENT = "relative_alpha_power"
NEW = ("lrtc_alpha", "icoh_alpha")
FAMILY = ("exponent_high", "exponent_low", "whole_head_exponent", "relative_delta_power",
          "relative_alpha_power", "lempel_ziv", "spectral_entropy", "spectral_edge_95",
          "multiscale_entropy_slope", "pac_slow_alpha", "critical_slowing_ar1",
          "wpli_alpha", "spatial_participation_ratio", "uce_v1") + NEW

MIN_SUBJECTS = 60
MAX_REDUNDANCY = 0.90
MDE = 0.272
E41_INCUMBENT_RHO = 0.2018
REPS = 20000
PERMS = 2000
SEED = 20260731


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def _rest():
    by = {}
    for path in sorted(glob.glob(REST_V2)):
        for r in csv.DictReader(open(path, newline="")):
            if r.get("status") == "ok":
                by.setdefault(r.get("subject", ""), []).append(r)
    return {s: {c: float(np.nanmean([_f(r.get(c, "")) for r in rs])) for c in FAMILY}
            for s, rs in by.items()}


def _labels(path, col="imagery_auc"):
    return {r["subject"]: _f(r[col]) for r in csv.DictReader(open(path, newline=""))
            if r.get("status") == "ok"}


def _corr(rest, lab, subs, name, rng, reps=REPS):
    x = np.array([rest[s].get(name, np.nan) for s in subs], float)
    y = np.array([lab[s] for s in subs], float)
    ok = np.isfinite(x) & np.isfinite(y)
    if ok.sum() < MIN_SUBJECTS:
        return None
    x, y = x[ok], y[ok]
    r = spearman(x, y)
    idx = np.arange(x.size)
    lo, hi, _ = cluster_bootstrap_ci(lambda i: spearman(x[i], y[i]), idx, rng, reps=reps)
    return {"rho": float(r), "ci": [float(lo), float(hi)], "n": int(x.size),
            "excludes_zero": bool(np.isfinite(lo) and np.isfinite(hi) and (lo > 0 or hi < 0))}


def main(argv=None) -> int:
    print("E42 — does alpha's TEMPORAL STRUCTURE carry what its MAGNITUDE does not?")
    print("   SECOND LOOK at this cohort: E41 scored 14 candidates here. Multiplicity uses all 16.")
    print("   The primary is TWO-SIDED: PMID 34618375's abstract gives no sign, and inventing one")
    print("   would be the over-reading rule 42 exists to prevent.")
    if not glob.glob(REST_V2):
        print(f"\n   *** no {os.path.basename(REST_V2)} present — extraction not finished.")
        return 2
    for p in (LABEL, EXEC_LABEL, RELIABILITY):
        if not os.path.exists(p):
            print(f"\n   *** {os.path.basename(p)} absent.")
            return 2
    rel = json.load(open(RELIABILITY))["p1"]
    rng = np.random.default_rng(SEED)
    rest, lab, lab_x = _rest(), _labels(LABEL), _labels(EXEC_LABEL)
    subs = sorted(set(rest) & set(lab))
    subs_x = sorted(set(rest) & set(lab_x))
    st = {"experiment": "E42", "ceiling": rel.get("ceiling"), "n_subjects": len(subs)}

    print("\n" + "=" * 100)
    print("G1 — COVERAGE AND CEILING")
    print("=" * 100)
    print(f"   subjects with a v2 resting row and an imagery label : {len(subs)}  (floor {MIN_SUBJECTS})")
    print(f"   E38 reliability {rel['r_sb']:+.4f} {rel['ci']}   ceiling {rel['ceiling']:.4f}")
    g1 = len(subs) >= MIN_SUBJECTS and bool(rel.get("viable"))
    print(f"   G1 {'PASSED' if g1 else '*** FAILED'}")
    st["g1"] = g1
    if not g1:
        print("   Nothing downstream is reported: ABSENT, not negative (rule 31).")
        json.dump(st, open(OUT, "w"), indent=2, default=float)
        return 1

    print("\n" + "=" * 100)
    print("G2 — THE REDUNDANCY GATE: is LRTC just alpha power again?")
    print("=" * 100)
    a = np.array([rest[s].get(PRIMARY, np.nan) for s in subs], float)
    b = np.array([rest[s].get(INCUMBENT, np.nan) for s in subs], float)
    ok = np.isfinite(a) & np.isfinite(b)
    red = spearman(a[ok], b[ok]) if ok.sum() >= MIN_SUBJECTS else float("nan")
    print(f"   Spearman({PRIMARY}, {INCUMBENT}) across {int(ok.sum())} subjects : {red:+.4f}"
          f"   (ceiling |{MAX_REDUNDANCY}|)")
    g2 = bool(np.isfinite(red) and abs(red) <= MAX_REDUNDANCY)
    print(f"   G2 {'PASSED' if g2 else '*** FAILED'}")
    st["g2"] = {"redundancy_with_incumbent": float(red), "passed": g2}
    if not g2:
        print("   LRTC is a restatement of alpha power in this cohort. The refinement's premise is false")
        print("   here regardless of any label, and no primary is reported.")
        st["verdict"] = "refuted_by_redundancy"
        json.dump(st, open(OUT, "w"), indent=2, default=float)
        return 1

    print("\n" + "=" * 100)
    print("P1 — THE INCUMBENT on the SAME rows")
    print("=" * 100)
    inc = _corr(rest, lab, subs, INCUMBENT, rng)
    print(f"   {INCUMBENT}  rho {inc['rho']:+.4f} [{inc['ci'][0]:+.4f}, {inc['ci'][1]:+.4f}]"
          f"   E41 measured {E41_INCUMBENT_RHO:+.4f} on the v1 table")
    st["p1"] = inc

    print("\n" + "=" * 100)
    print(f"P2 — THE PRIMARY: {PRIMARY}, two-sided")
    print("=" * 100)
    pri = _corr(rest, lab, subs, PRIMARY, rng)
    if pri is None:
        print("   too few subjects carry the primary. ABSENT.")
        st["verdict"] = "not_interpretable"
        json.dump(st, open(OUT, "w"), indent=2, default=float)
        return 1
    beats = abs(pri["rho"]) > abs(inc["rho"])
    print(f"   {PRIMARY}  rho {pri['rho']:+.4f} [{pri['ci'][0]:+.4f}, {pri['ci'][1]:+.4f}]")
    print(f"   excludes zero: {pri['excludes_zero']}   beats the incumbent: {beats}")
    p2 = bool(pri["excludes_zero"] and beats)
    print(f"   P2 {'PASSED' if p2 else '*** FAILED'}")
    st["p2"] = dict(pri, beats_incumbent=bool(beats), passed=p2)

    print("\n" + "=" * 100)
    print("P3 — PLACEBO: executed-movement decoding")
    print("=" * 100)
    if not pri["excludes_zero"]:
        print("   NOT INFORMATIVE: the primary spans zero, so there is nothing for the placebo to fail")
        print("   to reproduce (rule 48).")
        st["p3"] = {"status": "not_informative"}
        p3 = None
    else:
        plc = _corr(rest, lab_x, subs_x, PRIMARY, rng)
        print(f"   executed rho {plc['rho']:+.4f} [{plc['ci'][0]:+.4f}, {plc['ci'][1]:+.4f}]"
              f"   imagery {pri['rho']:+.4f}")
        p3 = bool(abs(pri["rho"]) > abs(plc["rho"]))
        print(f"   P3 {'PASSED' if p3 else '*** FAILED — the primary is WITHDRAWN'}")
        st["p3"] = dict(plc, passed=p3)

    print("\n" + "=" * 100)
    print("P5 — THE FULL TABLE, and the second registered redundancy check")
    print("=" * 100)
    per = {}
    for c in FAMILY:
        v = _corr(rest, lab, subs, c, rng, reps=600)
        if v:
            per[c] = v
            tag = "  <- PRIMARY" if c == PRIMARY else ("  <- incumbent" if c == INCUMBENT else "")
            print(f"   {c:28s} {v['rho']:+8.4f}  [{v['ci'][0]:+.4f}, {v['ci'][1]:+.4f}]{tag}")
    cs = np.array([rest[s].get("critical_slowing_ar1", np.nan) for s in subs], float)
    okc = np.isfinite(a) & np.isfinite(cs)
    r_cs = spearman(a[okc], cs[okc]) if okc.sum() >= MIN_SUBJECTS else float("nan")
    print(f"\n   Spearman({PRIMARY}, critical_slowing_ar1) = {r_cs:+.4f}"
          f"   — the candidate's second registered failure condition")
    st["p5"] = {"per_candidate": per, "redundancy_with_critical_slowing": float(r_cs)}

    print("\n" + "=" * 100)
    print("P4 — MULTIPLICITY over the FULL SIXTEEN, not the new pair")
    print("=" * 100)
    names = [c for c in FAMILY if c in per]
    X = np.array([[rest[s].get(c, np.nan) for c in names] for s in subs], float)
    y = np.array([lab[s] for s in subs], float)
    ok = np.isfinite(y) & np.all(np.isfinite(X), axis=1)
    Xo, yo = X[ok], y[ok]
    obs = [abs(spearman(Xo[:, j], yo)) for j in range(len(names))]
    null = np.empty((PERMS, len(names)), float)
    for k in range(PERMS):
        yp = rng.permutation(yo)
        for j in range(len(names)):
            null[k, j] = abs(spearman(Xo[:, j], yp))
    wy = westfall_young_maxt(obs, np.nan_to_num(null, nan=0.0), names=names)
    print(f"   effective_tests {wy['effective_tests']:.2f} of {wy['n_candidates']}  (n={int(ok.sum())})")
    surv = [n for n in names if wy["adjusted"][n] <= 0.05]
    print(f"   surviving FWER 0.05: {surv if surv else 'none'}")
    for n in (PRIMARY, INCUMBENT, "icoh_alpha"):
        if n in wy["raw"]:
            print(f"      {n:28s} raw p {wy['raw'][n]:.4f}   adjusted p {wy['adjusted'][n]:.4f}")
    st["p4"] = {"effective_tests": wy["effective_tests"], "adjusted": wy["adjusted"],
                "raw": wy["raw"], "survivors": surv}

    print("\n" + "=" * 100)
    print("VERDICT")
    print("=" * 100)
    if not pri["excludes_zero"] and abs(pri["rho"]) < MDE:
        verdict = "underpowered_null"
        print(f"   UNDERPOWERED NULL: |rho| = {abs(pri['rho']):.3f} below the design's minimum detectable")
        print(f"   effect of {MDE:.3f}. **Not a negative** — same cohort, same limit as E41.")
    elif not p2:
        verdict = "not_met"
        print("   NOT MET: the primary does not both exclude zero and beat the incumbent.")
    elif p3 is False:
        verdict = "withdrawn_placebo"
        print("   WITHDRAWN: executed movement is predicted as well, so this tracks cortical legibility.")
    else:
        verdict = "refined"
        print(f"   REFINED: {PRIMARY} rho {pri['rho']:+.4f} exceeds alpha power's {inc['rho']:+.4f},")
        print(f"   against a ceiling of {rel['ceiling']:.3f}. Report the 16-candidate adjusted p beside it.")
    st["verdict"] = verdict
    json.dump(st, open(OUT, "w"), indent=2, default=float)
    print(f"\n   wrote results/{os.path.basename(OUT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
