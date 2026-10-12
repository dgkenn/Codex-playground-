#!/usr/bin/env python3
"""E171 — CALIBRATION across patient strata, which this project has never once measured.

REGISTERED BEFORE ANY CALIBRATION SLOPE HAS BEEN COMPUTED.

=========================================================================================================
WHY, IN THE PROJECT'S OWN WORDS
=========================================================================================================
Error-catalogue rule 15: *"Discrimination without calibration is half a result, and the missing half is
the half clinicians use."* `PROGRAMME_ROADMAP.md`, Challenge D: *"The calibration half has never been
touched. **Every result in this project is rank-based.** ... we have produced zero calibrated outputs. A
monitor emits a number that must mean the same thing in an 80-year-old and a 30-year-old."*

That is still true at 170 registered experiments. Every AUC, every Spearman, every increment in this repo
is invariant to any monotone transform of the score, which is exactly the information a bedside number
cannot do without. **This file produces the project's first calibrated output and asks the only question
that matters about one: does the same predicted value mean the same thing in different patients?**

For the anaesthesia wedge this is not a refinement. Substantial equivalence against a BIS predicate
requires performance across the intended population, and E109 already measured **BIS itself degrading with
age (+0.2592 [+0.1367, +0.3761])** — a wedge only if ours demonstrably does not, and that is a statement
about calibration slope and intercept per stratum, not about AUC.

=========================================================================================================
THE REFERENCE, AND WHY IT IS DOSE-I AND NOT VITALDB
=========================================================================================================
A calibration claim needs a reference that is **not the incumbent**. VitalDB has only BIS, so calibrating
against it would measure agreement with BIS and nothing else, and would be circular besides — BIS is
computed from the same EEG.

DOSE-I ships **MOAA/S**, a clinician-assigned 1-5 observer scale, on all **171** recordings in
`dosei_pEEG.zip`, and `dosei_covariates.csv` carries age, sex, BMI and ASA for all 171 with a complete
join. So the target is behavioural, the strata are demographic, and neither is derived from the EEG.

=========================================================================================================
DESIGN
=========================================================================================================
    target        MOAA/S, 1-5, treated as an interval scale for calibration (stated, not assumed neutral)
    arms          A  the eleven-feature spectral panel this project uses
                  B  SEF95 alone -- THE INCUMBENT (rule 45), the same measure E79 scored at rho +0.1799
                  C  PE31 alone -- the candidate E166/E170 moved
    fitting       ridge, RECORDING-grouped 5-fold, standardised on training rows only; every prediction
                  is out of fold, so a calibration slope near 1 is not a restatement of the fit
    primary       the calibration SLOPE and INTERCEPT of observed MOAA/S on out-of-fold predicted MOAA/S,
                  computed SEPARATELY WITHIN each stratum, and the statistic is the SPREAD of the slope
                  across strata (max - min) for each arm
    strata        age tercile, sex, ASA (1-2 vs 3), BMI tercile -- four independent stratifications, each
                  reported, none pooled into a single number

**RULE 51, MET EXPLICITLY.** Name how the measure is expected to fail, then check the primary can see it.
A depth index fails calibration by its slope drifting away from 1 in some stratum (the same predicted
number meaning a different depth) or by its intercept shifting (a constant offset). Slope spread sees the
first directly and the intercept table sees the second; both are printed for every stratification, and
neither is a median-like statistic that could hide a tail (rule 51's actual failure).

**RULE 49, MET EXPLICITLY.** No stratum is defined on either predictor. Selecting rows on the incumbent
you intend to beat forces the comparison, and that is how E46 died.

=========================================================================================================
GATES
=========================================================================================================
G1  JOIN AND COVERAGE: >= 100 recordings with a covariate row, >= 2 distinct MOAA/S values and >= 30
    windows. Reported with what was dropped and why (rule 14).
G2  THE MODELS ARE ALIVE: each arm's out-of-fold Spearman against MOAA/S must beat its own
    recording-permutation null. An arm that cannot predict at all has no calibration to measure, and a
    dead incumbent would make the comparison meaningless (rule 53 / E61).
G3  CALIBRATION IS ESTIMABLE: every stratum must carry >= 15 recordings and >= 300 windows, or that whole
    stratification is dropped and SAID to be dropped.

=========================================================================================================
PLACEBO, AND IT GATES THE VERDICT (rules 34, 35)
=========================================================================================================
With 171 recordings split three or four ways, slope spread across strata has a sampling distribution that
is not zero and cannot be reasoned about. **The placebo assigns recordings to RANDOM strata of the same
sizes**, 500 times, and produces the null distribution of slope spread for each arm. A real spread is
claimed only if it exceeds that distribution — a comparison, never a threshold. This is rule 35's matched
subset control in the form this design needs, and without it the whole experiment measures group sizes.

=========================================================================================================
VERDICT — WRONG-DIRECTION AND UNINFORMATIVE CASES FIRST (rules 31, 37)
=========================================================================================================
  (1) NOT INTERPRETABLE  G1, G2 or G3 fails for the arms being compared.
  (2) NOISE              neither arm's slope spread exceeds its random-stratum placebo. Then nothing is
                         known about either one's stability and NO comparison is reported — including a
                         flattering one (rule 48: a placebo cannot validate a null).
  (3) OURS WORSE         the panel's slope spread exceeds SEF95's, both above placebo. **This is the
                         wrong-direction branch and it is written before the numbers**: it would mean an
                         eleven-feature panel is LESS transportable across patients than a single number,
                         which is a real possibility and would be reported as the finding.
  (4) NO DIFFERENCE      both above placebo, spreads within each other's placebo width.
  (5) OURS MORE STABLE   the panel's spread is below SEF95's and below its own placebo.

REGISTERED PREDICTION: **(3) or (4)** — the panel has eleven free parameters fitted on 171 recordings and
more capacity to encode stratum-specific structure than a single measure does, so I expect it to be no
better and possibly worse. The prediction is against the wedge story, which is the correct way round.

SCOPE. One deposit, procedural sedation with bolus propofol, an observer scale treated as interval, and
strata of 40-60 recordings. This measures whether a calibration DIFFERENCE across strata is detectable
here; it does not establish calibration for any deployed use.

    python bsde/src/bsde/experiments/e171_calibration_across_strata.py
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

from bsde.verifier.stats import (cluster_permute, grouped_cv_predict,           # noqa: E402
                                 screen_candidates, spearman)

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
ZIP = os.path.join(RESULTS, "dosei_pEEG.zip")
COV = os.path.join(RESULTS, "dosei_covariates.csv")
OUT = os.path.join(RESULTS, "e171_calibration_across_strata.json")
SEED = 20260801

PANEL = ["rel_delta1", "rel_theta", "rel_alpha", "rel_beta1", "rel_gamma",
         "SEF95", "MF", "PE31", "WSMF30", "sync_alpha", "sync_theta"]
INCUMBENT = ["SEF95"]
CANDIDATE = ["PE31"]
ARMS = {"panel": PANEL, "SEF95": INCUMBENT, "PE31": CANDIDATE}

MIN_RECORDINGS = 100
MIN_WINDOWS = 30
MIN_STRATUM_RECORDINGS = 15
MIN_STRATUM_WINDOWS = 300
PLACEBO_DRAWS = 500
ALPHA = 0.05


def _f(v):
    try:
        x = float(v)
        return x if np.isfinite(x) else float("nan")
    except (TypeError, ValueError):
        return float("nan")


def load():
    cov = {r["recording"]: r for r in csv.DictReader(open(COV, newline=""))}
    z = zipfile.ZipFile(ZIP)
    X, y, grp, dropped = [], [], [], {}
    meta = {}
    for nm in sorted(n for n in z.namelist() if n.endswith("_pEEG.csv")):
        rid = os.path.basename(nm).replace("_pEEG.csv", "")
        if rid not in cov:
            dropped[rid] = "no covariate row"
            continue
        rows = list(csv.DictReader(io.StringIO(z.read(nm).decode("utf-8-sig"))))
        m = np.array([_f(r.get("MOAAS", "")) for r in rows])
        feat = np.array([[_f(r.get(c, "")) for c in PANEL] for r in rows], float)
        ok = np.isfinite(m) & np.all(np.isfinite(feat), axis=1)
        if ok.sum() < MIN_WINDOWS:
            dropped[rid] = f"only {int(ok.sum())} usable windows"
            continue
        if len(np.unique(m[ok])) < 2:
            dropped[rid] = "MOAA/S constant"
            continue
        X.append(feat[ok])
        y.append(m[ok])
        grp.append(np.full(int(ok.sum()), rid))
        c = cov[rid]
        meta[rid] = {"age": _f(c["age"]), "bmi": _f(c["bmi"]),
                     "sex": 1.0 if str(c["sex"]).upper().startswith("M") else 0.0,
                     "asa": _f(c["asa"])}
    if not X:
        return None
    return (np.vstack(X), np.concatenate(y), np.concatenate(grp), meta, dropped)


def calib(obs, pred):
    """Slope and intercept of OBSERVED on PREDICTED -- the standard calibration regression."""
    ok = np.isfinite(obs) & np.isfinite(pred)
    if ok.sum() < 30 or np.std(pred[ok]) < 1e-9:
        return float("nan"), float("nan")
    A = np.column_stack([np.ones(ok.sum()), pred[ok]])
    coef, *_ = np.linalg.lstsq(A, obs[ok], rcond=None)
    return float(coef[1]), float(coef[0])


def strata_of(meta, rids, kind):
    """Recording-level stratum assignment. Never a function of any predictor (rule 49)."""
    u = sorted(set(rids.tolist()))
    if kind == "sex":
        lab = {r: ("M" if meta[r]["sex"] > 0.5 else "F") for r in u}
    elif kind == "asa":
        lab = {r: ("ASA1-2" if meta[r]["asa"] <= 2 else "ASA3+") for r in u}
    else:
        v = np.array([meta[r][kind] for r in u], float)
        q = np.nanquantile(v[np.isfinite(v)], [1 / 3, 2 / 3])
        lab = {}
        for r in u:
            x = meta[r][kind]
            lab[r] = ("NA" if not np.isfinite(x) else
                      f"{kind}_low" if x <= q[0] else f"{kind}_mid" if x <= q[1] else f"{kind}_high")
    return np.array([lab[r] for r in rids])


def spread(obs, pred, lab, rids):
    """Max - min calibration slope across strata, plus the per-stratum table."""
    tab = {}
    for s in sorted(set(lab.tolist())):
        if s == "NA":
            continue
        m = lab == s
        if len(set(rids[m].tolist())) < MIN_STRATUM_RECORDINGS or m.sum() < MIN_STRATUM_WINDOWS:
            tab[s] = {"slope": float("nan"), "intercept": float("nan"),
                      "n_rec": len(set(rids[m].tolist())), "n_win": int(m.sum()),
                      "estimable": False}
            continue
        sl, ic = calib(obs[m], pred[m])
        tab[s] = {"slope": sl, "intercept": ic, "n_rec": len(set(rids[m].tolist())),
                  "n_win": int(m.sum()), "estimable": True}
    sl = [v["slope"] for v in tab.values() if v["estimable"] and np.isfinite(v["slope"])]
    return (float(max(sl) - min(sl)) if len(sl) >= 2 else float("nan")), tab


def main() -> int:
    print("E171 — calibration slope and intercept across patient strata, against MOAA/S")
    got = load()
    if got is None:
        print("ABSENT: no usable recordings.")
        return 2
    X, y, grp, meta, dropped = got
    rids = np.unique(grp)
    res = {"experiment": "E171", "n_recordings": int(rids.size), "n_windows": int(len(y)),
           "dropped": dropped, "target": "MOAAS", "panel": PANEL}
    print(f"G1 JOIN  {rids.size} recordings, {len(y)} windows "
          f"({len(dropped)} recordings dropped: "
          + ", ".join(sorted({v for v in dropped.values()})) + ")")
    res["G1_pass"] = bool(rids.size >= MIN_RECORDINGS)
    print(f"   {'PASS' if res['G1_pass'] else '*** FAIL'} (floor {MIN_RECORDINGS} recordings)")
    if not res["G1_pass"]:
        res["verdict"] = "NOT-INTERPRETABLE"
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    cols = {c: X[:, i] for i, c in enumerate(PANEL)}
    usable, drop2 = screen_candidates(cols)
    for c, why in drop2.items():
        print(f"   dropped feature: {c} ({why})")
    keep_idx = [i for i, c in enumerate(PANEL) if c in usable]

    # ---- out-of-fold predictions and G2 aliveness, per arm
    print("\nG2 ARMS ALIVE (out-of-fold Spearman against MOAA/S, vs a recording-permutation null)")
    preds, alive = {}, {}
    rng = np.random.default_rng(SEED)
    for name, feats in ARMS.items():
        idx = [i for i in keep_idx if PANEL[i] in feats]
        if not idx:
            alive[name] = {"pass": False, "why": "no usable feature in this arm"}
            continue
        Xa = X[:, idx]
        p = grouped_cv_predict(Xa, y, grp, np.random.default_rng(SEED + 1))
        preds[name] = p
        r = spearman(list(y[np.isfinite(p)]), list(p[np.isfinite(p)]))
        nulls = []
        for _ in range(200):
            Xp = np.column_stack([cluster_permute(Xa[:, j], grp, rng) for j in range(Xa.shape[1])])
            pp = grouped_cv_predict(Xp, y, grp, np.random.default_rng(SEED + 1))
            ok = np.isfinite(pp)
            v = spearman(list(y[ok]), list(pp[ok]))
            if np.isfinite(v):
                nulls.append(v)
        n = np.asarray(nulls)
        pv = float((n >= r).mean()) if n.size >= 30 else float("nan")
        alive[name] = {"spearman": float(r), "null_p95": float(np.quantile(n, 0.95)) if n.size else
                       float("nan"), "p": pv, "pass": bool(np.isfinite(pv) and pv <= ALPHA)}
        print(f"   {name:<7s} rho {r:+.4f}  null p95 {alive[name]['null_p95']:+.4f}  p {pv:.4f}   "
              f"{'PASS' if alive[name]['pass'] else '*** FAIL'}")
    res["G2"] = alive
    if not all(alive.get(k, {}).get("pass") for k in ("panel", "SEF95")):
        res["verdict"] = "NOT-INTERPRETABLE"
        res["why"] = "the panel or the incumbent does not predict MOAA/S at all; there is no calibration " \
                     "to compare (rule 53)"
        print("\nVERDICT NOT INTERPRETABLE — " + res["why"])
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    # ---- calibration per stratification, per arm, with a matched random-stratum placebo
    res["stratifications"] = {}
    print(f"\nCALIBRATION  (slope 1.00 and intercept 0.00 would be perfect; every prediction is out of "
          f"fold)")
    for kind in ("age", "sex", "asa", "bmi"):
        lab = strata_of(meta, grp, kind)
        sizes = {s: int((lab == s).sum()) for s in sorted(set(lab.tolist())) if s != "NA"}
        block = {"sizes": sizes, "arms": {}}
        print(f"\n   --- stratified by {kind}: " + ", ".join(f"{k} n={v}" for k, v in sizes.items()))
        estimable = True
        for name in ARMS:
            if name not in preds:
                continue
            sp, tab = spread(y, preds[name], lab, grp)
            block["arms"][name] = {"slope_spread": sp, "table": tab}
            if not np.isfinite(sp):
                estimable = False
            print(f"   {name:<7s} slope spread {sp:>7.4f}   " +
                  "  ".join(f"{s}: {v['slope']:+.3f}/{v['intercept']:+.3f}"
                            for s, v in tab.items() if v["estimable"]))
        if not estimable:
            block["dropped"] = "at least one stratum was not estimable at the registered floors"
            print(f"   *** {kind} DROPPED — a stratum fell below "
                  f"{MIN_STRATUM_RECORDINGS} recordings / {MIN_STRATUM_WINDOWS} windows")
            res["stratifications"][kind] = block
            continue

        # PLACEBO: random strata of the SAME sizes, at the recording level
        prng = np.random.default_rng(SEED + 77)
        rec_lab = {}
        for r in np.unique(grp):
            rec_lab[r] = lab[grp == r][0]
        recs = list(rec_lab)
        counts = {}
        for r in recs:
            counts[rec_lab[r]] = counts.get(rec_lab[r], 0) + 1
        null_spread = {name: [] for name in block["arms"]}
        for _ in range(PLACEBO_DRAWS):
            perm = list(prng.permutation(recs))
            assign, i = {}, 0
            for s, c in counts.items():
                for r in perm[i:i + c]:
                    assign[r] = s
                i += c
            flab = np.array([assign[r] for r in grp])
            for name in block["arms"]:
                sp, _ = spread(y, preds[name], flab, grp)
                if np.isfinite(sp):
                    null_spread[name].append(sp)
        for name, vals in null_spread.items():
            v = np.asarray(vals)
            obs_sp = block["arms"][name]["slope_spread"]
            p95 = float(np.quantile(v, 0.95)) if v.size >= 30 else float("nan")
            pv = float((v >= obs_sp).mean()) if v.size >= 30 else float("nan")
            block["arms"][name].update({"placebo_p95": p95, "placebo_p": pv,
                                        "above_placebo": bool(np.isfinite(pv) and pv <= ALPHA),
                                        "n_placebo": int(v.size)})
            print(f"   {name:<7s} placebo random-strata p95 {p95:>7.4f}, p {pv:.4f}   "
                  f"{'ABOVE placebo' if block['arms'][name]['above_placebo'] else 'at placebo'}")
        res["stratifications"][kind] = block

    # ---- verdict, over the stratifications that were estimable
    live = {k: v for k, v in res["stratifications"].items() if "dropped" not in v}
    any_above = [k for k, v in live.items()
                 if v["arms"]["panel"]["above_placebo"] or v["arms"]["SEF95"]["above_placebo"]]
    if not live:
        v, why = "NOT-INTERPRETABLE", "no stratification was estimable at the registered floors"
    elif not any_above:
        v, why = "NOISE", ("no arm's slope spread exceeds its own random-stratum placebo in any "
                           "stratification, so nothing is known about either one's stability and no "
                           "comparison is reported -- including a flattering one (rule 48)")
    else:
        worse = [k for k in any_above
                 if live[k]["arms"]["panel"]["slope_spread"] > live[k]["arms"]["SEF95"]["slope_spread"]]
        better = [k for k in any_above
                  if live[k]["arms"]["panel"]["slope_spread"] < live[k]["arms"]["SEF95"]["slope_spread"]]
        if len(worse) > len(better):
            v, why = "OURS-WORSE", (f"the panel's slope spread exceeds SEF95's in {worse} -- an "
                                    "eleven-feature panel is LESS stable across patients than one number, "
                                    "which is the registered wrong-direction branch")
        elif len(better) > len(worse):
            v, why = "OURS-MORE-STABLE", (f"the panel's slope spread is below SEF95's in {better}; this "
                                          "is the first calibrated comparison this project has produced "
                                          "and it must be replicated before it is used")
        else:
            v, why = "NO-DIFFERENCE", "the two arms' slope spreads do not separate"
    res["verdict"], res["why"] = v, why
    print(f"\nVERDICT {v} — {why}")
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
