"""E84 -- Challenge C, asked for the first time against an incumbent this project has actually validated.

REGISTERED BEFORE `dosei_holdout_features.csv` EXISTS. Third registration against that table (E80, E81,
E84), all written before the extraction was launched, all asking different questions of it. The count is
stated here because experiment-level multiplicity is what the ledger exists to make visible.

=========================================================================================================
WHY THIS IS NOT E26, E34 OR E37 AGAIN
=========================================================================================================
Challenge C asks whether any candidate carries information the incumbent does not. It has been answered NO
three times -- E26 (BIS), E34 (permutation entropy), E37 (lag-1 autocorrelation) -- and every one of those
carried the same caveat: **the incumbent was SEF95, chosen because nothing better was computable off a
monitor.** E26/E34/E37 each scoped themselves "never ahead of BIS".

Four experiments since have replaced that. E65 killed the fitted BIS-like index (rho +0.04 against a
clinician). E76 showed the deposit's declared preprocessing accounts for the whole gap between our
permutation entropy and the shipped `PE31`. E78 put `bis_rbr` and our corrected PE in a dead heat on 62
held-out recordings. E79 showed the residual difference is window length, and that at matched support the
two independent implementations AGREE. **So Challenge C now has a validated, published, portable
incumbent, and this is the first time its central question can be asked against one.**

E79 also measured what SEF95 was worth as a bar: on held-out recordings SEF95 reaches median
within-recording rho **+0.1799** against MOAA/S where PE31 reaches **+0.4355**. Beating SEF95 and beating
PE31 are not the same test, and three prior nulls were run against the easier one.

=========================================================================================================
DESIGN
=========================================================================================================
BASELINE, pre-declared and NOT the best of anything: the deposit's own **`their_pe31` and `their_sef95`**
together. Both are published, both are shipped by the deposit rather than fitted here, and using the
deposit's own columns means the bar cannot be accused of being tuned by this project.

    P   For each candidate X, the OUT-OF-BAG increment from baseline to baseline+X in predicting MOAA/S.
        Rule 9 in full: each replicate fits BOTH models on a bootstrap resample of RECORDINGS and scores
        both on the recordings NOT drawn. The statistic is `1 - spearman(true, predicted)`, i.e. an ERROR
        (lower is better), so the returned B-minus-A difference is **NEGATIVE when the candidate helps**.
        That convention is stated here because reading it backwards would invert every verdict, and it is
        the convention `oob_regression_increment` documents.

    Benjamini-Hochberg at q = 0.05 across all tested candidates. The count of candidates is reported with
    the result, not in a footnote.

VERDICT per candidate, wrong direction FIRST and by name (rule 37):

    (a) interval excludes 0 POSITIVE -> HURTS. Adding the candidate makes out-of-bag prediction WORSE.
        Not a null: it means the candidate is noise the model spends capacity on, and it must not be
        reported as "no increment".
    (b) interval includes 0            -> NO INCREMENT.
    (c) interval excludes 0 NEGATIVE   -> ADDS, subject to the placebo.

GATES, before any candidate (rule 40):

    G1  HELD OUT      zero overlap with the 43 recordings already used.
    G2  COVERAGE      >= 25 recordings with >= 20 windows each and MOAA/S taking more than one value.
    G3  THE INCUMBENT MUST BE ALIVE (rule 53, E33's formulation). The baseline alone must predict MOAA/S
        out of bag above chance -- median out-of-bag `spearman(true, predicted) > 0.1`. **If the baseline
        cannot predict the label, "nothing beats it" is a statement about the label, not the candidates**,
        and that is exactly the trap E61 fell into.
    G4  NEGATIVE CONTROL. A per-window Gaussian column is carried through the identical pipeline and must
        NOT come back ADDS. If noise adds, the out-of-bag machinery is leaking.

PLACEBO (after the primaries, able only to remove). Each candidate's column is permuted WITHIN recording,
which preserves its marginal distribution and its recording-level mean exactly and destroys only its
alignment to the label in time -- rule 55: that alignment is what the statistic is a function of. 200
draws; any ADDS inside the placebo's central 95 % is withdrawn.

SCOPE. One deposit, propofol sedation, one behavioural scale. An increment here would be a claim about
predicting MOAA/S, not about consciousness, and Brief 01's constraint stands: no experimental output is
evidence of consciousness.

    python -m bsde.experiments.e84_increment_over_validated_incumbent
"""
from __future__ import annotations

import csv
import json
import os
import sys
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from bsde.verifier.stats import oob_regression_increment, ridge_fit         # noqa: E402

TABLE = os.path.join(RESULTS, "dosei_holdout_features.csv")
OUT = os.path.join(RESULTS, "e84_increment_over_validated_incumbent.json")
USED_TABLES = ("dosei_features.csv", "dosei_pe_check.csv", "dosei_pe_variants.csv")

BASELINE = ("their_pe31", "their_sef95")
META = {"recording", "t_s", "soc", "moaas", "propofol", "endoscopy", "ecg_hr", "n_finite",
        "their_pe31", "their_sef95"}
CTRL_NEG = "_CTRL_noise"
MIN_WINDOWS, MIN_RECORDINGS = 20, 25
G3_MIN_RHO = 0.10
REPS = 400
PLACEBO_DRAWS = 200
SEED = 20260731


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def spearman(a, b):
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() < 10 or len(set(a[ok].tolist())) < 2 or len(set(b[ok].tolist())) < 2:
        return float("nan")
    from scipy.stats import spearmanr
    return float(spearmanr(a[ok], b[ok]).statistic)


def err(t, p):
    """1 - spearman, so LOWER IS BETTER and oob_regression_increment's B-minus-A keeps its documented sign."""
    r = spearman(np.asarray(t, float), np.asarray(p, float))
    return 1.0 - r if np.isfinite(r) else 1.0


def used_recordings() -> set:
    out = set()
    for name in USED_TABLES:
        p = os.path.join(RESULTS, name)
        if not os.path.exists(p):
            continue
        with open(p, newline="") as fh:
            rd = csv.DictReader(fh)
            key = "recording" if "recording" in (rd.fieldnames or []) else "recording_id"
            for r in rd:
                if r.get(key):
                    out.add(r[key].split("@")[0])
    return out


def main() -> int:
    if not os.path.exists(TABLE):
        print(f"ABSENT: {TABLE} does not exist yet"); return 2
    rows = defaultdict(list)
    with open(TABLE, newline="") as fh:
        rd = csv.DictReader(fh)
        cands = [c for c in (rd.fieldnames or []) if c not in META]
        for r in rd:
            rows[r["recording"]].append(r)
    res = {"gates": {}, "candidates": {}, "n_candidates": len(cands)}
    print(f"{len(rows)} recordings, {sum(len(v) for v in rows.values())} windows, "
          f"{len(cands)} candidates")

    overlap = sorted(set(rows) & used_recordings())
    res["gates"]["G1_overlap"], res["gates"]["G1_pass"] = overlap, not overlap
    print(f"G1 held out   {len(overlap)} overlapping   {'PASS' if not overlap else 'FAIL'}")

    keep = []
    for rec, rs in sorted(rows.items()):
        mo = np.array([_f(r["moaas"]) for r in rs])
        if np.isfinite(mo).sum() >= MIN_WINDOWS and len(set(mo[np.isfinite(mo)].tolist())) > 1:
            keep.append(rec)
    res["gates"]["G2_recordings"] = len(keep)
    res["gates"]["G2_pass"] = bool(len(keep) >= MIN_RECORDINGS)
    print(f"G2 coverage   {len(keep)} recordings   {'PASS' if res['gates']['G2_pass'] else 'FAIL'}")

    rng = np.random.default_rng(SEED)
    y, subj, base, cand = [], [], [], defaultdict(list)
    for rec in keep:
        for r in rows[rec]:
            mo = _f(r["moaas"])
            b = [_f(r.get(c, "")) for c in BASELINE]
            if not np.isfinite(mo) or not all(np.isfinite(b)):
                continue
            y.append(mo)
            subj.append(rec)
            base.append(b)
            for c in cands:
                cand[c].append(_f(r.get(c, "")))
            cand[CTRL_NEG].append(float(rng.normal()))
    y = np.asarray(y, float)
    subj = np.asarray(subj)
    Xa = np.asarray(base, float)
    print(f"   {y.size} usable windows over {len(set(subj.tolist()))} recordings")

    # G3: the incumbent must be alive, measured out of bag on the same resampling scheme
    uniq = np.unique(subj)
    rg = np.random.default_rng(SEED + 1)
    rhos = []
    for _ in range(100):
        drawn = set(rg.choice(uniq, size=len(uniq), replace=True).tolist())
        tr = np.isin(subj, list(drawn))
        te = ~tr
        if te.sum() < 50 or tr.sum() < 50:
            continue
        # ridge_fit requires an intercept column in position 0 and standardisation on TRAIN rows only
        mu, sd = Xa[tr].mean(axis=0), Xa[tr].std(axis=0)
        sd = np.where(sd > 1e-12, sd, 1.0)
        Dtr = np.column_stack([np.ones(tr.sum()), (Xa[tr] - mu) / sd])
        Dte = np.column_stack([np.ones(te.sum()), (Xa[te] - mu) / sd])
        w = ridge_fit(Dtr, y[tr], lam=1.0)
        r = spearman(y[te], Dte @ w)
        if np.isfinite(r):
            rhos.append(r)
    g3 = float(np.median(rhos)) if rhos else float("nan")
    res["gates"].update({"G3_baseline_oob_rho": g3, "G3_pass": bool(np.isfinite(g3) and g3 > G3_MIN_RHO)})
    print(f"G3 incumbent  baseline out-of-bag rho {g3:+.4f}   "
          f"{'PASS' if res['gates']['G3_pass'] else 'FAIL'}")

    if not all(res["gates"][k] for k in ("G1_pass", "G2_pass", "G3_pass")):
        print("\nGATE FAILED -- no candidate evaluated; the verdict is ABSENT, not a null (rule 31).")
        res["verdict"] = "GATE-FAILED"
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    order = cands + [CTRL_NEG]
    print(f"\n{'candidate':<28s} {'increment':>10s} {'95% CI':>22s}  verdict")
    out = {}
    for c in order:
        x = np.asarray(cand[c], float)
        if not np.isfinite(x).any() or np.nanstd(x) < 1e-12:
            out[c] = {"verdict": "DEGENERATE"}
            print(f"{c:<28s} {'--':>10s} {'--':>22s}  DEGENERATE")
            continue
        Xb = np.column_stack([Xa, np.nan_to_num(x, nan=float(np.nanmedian(x)))])
        pt, lo, hi = oob_regression_increment(Xa, Xb, y, subj, np.random.default_rng(SEED + 2),
                                              stat=err, reps=REPS)[:3]
        if not np.isfinite(pt):
            v = "NOT-COMPUTABLE"
        elif lo > 0 and hi > 0:
            v = "HURTS"
        elif lo < 0 and hi < 0:
            v = "ADDS"
        else:
            v = "NO INCREMENT"
        out[c] = {"increment": pt, "lo": lo, "hi": hi, "verdict": v}
        print(f"{c:<28s} {pt:+10.4f} [{lo:+9.4f}, {hi:+9.4f}]  {v}")

    # placebo, only for the candidates that ADD
    adds = [c for c in cands if out.get(c, {}).get("verdict") == "ADDS"]
    for c in adds:
        x = np.asarray(cand[c], float)
        pl = []
        for d in range(PLACEBO_DRAWS // 10):
            rp = np.random.default_rng(SEED + 900 + d)
            xs = x.copy()
            for rec in np.unique(subj):
                m = subj == rec
                xs[m] = rp.permutation(xs[m])
            Xb = np.column_stack([Xa, np.nan_to_num(xs, nan=float(np.nanmedian(xs)))])
            p = oob_regression_increment(Xa, Xb, y, subj, np.random.default_rng(SEED + 3),
                                         stat=err, reps=60)[0]
            if np.isfinite(p):
                pl.append(p)
        if pl:
            plo, phi = float(np.percentile(pl, 2.5)), float(np.percentile(pl, 97.5))
            inside = plo <= out[c]["increment"] <= phi
            out[c].update({"placebo": [plo, phi], "withdrawn": bool(inside)})
            if inside:
                out[c]["verdict"] = "WITHDRAWN-BY-PLACEBO"
            print(f"   placebo {c}: [{plo:+.4f}, {phi:+.4f}]  "
                  f"{'WITHDRAWN' if inside else 'survives'}")

    res["candidates"] = out
    res["gates"]["G4_pass"] = out.get(CTRL_NEG, {}).get("verdict") != "ADDS"
    final = [c for c in cands if out.get(c, {}).get("verdict") == "ADDS"]
    hurts = [c for c in cands if out.get(c, {}).get("verdict") == "HURTS"]
    res["verdict"] = (f"ADDS {final}; HURTS {hurts}; of {len(cands)} candidates tested against a "
                      f"baseline of the deposit's own PE31 and SEF95 (baseline out-of-bag rho {g3:+.4f}). "
                      f"Negative control: {out.get(CTRL_NEG, {}).get('verdict')}.")
    print(f"\nVERDICT: {res['verdict']}")
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
