#!/usr/bin/env python3
"""E73 -- Challenge B. Does a resting NETWORK measure predict BCI ability, where amplitude summaries did not?

REGISTERED WHILE THE FEATURE EXTRACTION IS STILL RUNNING AND BEFORE ANY FEATURE HAS BEEN RELATED TO ANY
ACCURACY. One pilot session (S1, session 1) was inspected to confirm the columns populate and that its
accuracy matches the label pass exactly (0.636905). No correlation of any kind has been computed.

=========================================================================================================
WHY THIS CAN FINALLY BE ASKED
=========================================================================================================
E41 returned Challenge B's null: `uce_v1` at rho = +0.0853 [-0.1066, +0.2651] against an incumbent
`relative_alpha_power` at +0.2018, with nothing surviving multiplicity. **That null was never
interpretable.** E38 measured eegmmidb's label reliability at 0.2918, capping any predictor at **0.5402**
by attenuation alone, against a minimum detectable effect of 0.272.

E68 measured this deposit's ceiling instead: **0.9652 [0.9568, 0.9706]** within session, **0.8087** for a
stable-ability design, **0.9478** for a change score. Q14's precondition -- measure the ceiling before the
correlation -- is met, so **a null here would be a real null**.

**And the family being tested changes.** Every Challenge B candidate this project has run is an amplitude
summary. The literature's working predictors are network measures: resting-state efficiency and clustering
(PMID 26529439), microstates at AUC 0.83 against a spectral-entropy incumbent (PMID 37759889), and a
three-dataset survey whose point is that connectivity metric and band change the answer (PMID 38986469).
Stieger's 62 channels carry inter-channel phase; every previous Challenge B deposit could not.

=========================================================================================================
DESIGN
=========================================================================================================
**THE PRIMARY IS ONE PRE-DECLARED MEASURE, NOT THE BEST OF FOURTEEN.** `wpli_alpha_global_efficiency`,
**predicted POSITIVE**, because PMID 26529439 reports global efficiency positively correlated with MI
classification accuracy. Taking a maximum over a family would be biased upward and is not done; the family
is reported separately with multiplicity control and is explicitly not the primary.

TWO DESIGNS, ANSWERING DIFFERENT QUESTIONS AND CAPPED BY DIFFERENT CEILINGS (E68):

  D1 BETWEEN-SUBJECT   subject-mean feature against subject-mean accuracy. Capped near **sqrt(R2) = 0.8087**,
                       because the part of a session's score that does not persist is not a property of the
                       subject. This is E41's question asked on a better label.
  D2 WITHIN-SUBJECT    consecutive-session CHANGE in feature against change in accuracy, subject-clustered.
                       Capped near **0.9478**. Q28's design: immune to every stable between-subject
                       confound, and the one a state-like measure can win (E45 found `lempel_ziv` is a
                       state, not a trait -- which retrodicts E41's null).

  G1 COVERAGE   >= `MIN_SUBJECTS` subjects for D1 and >= `MIN_PAIRS` consecutive pairs for D2.
  G2 CAPABILITY the primary must VARY -- non-degenerate across subjects -- or a null is about the extractor
                rather than the brain (rule 53).
  P1 INCUMBENT  `relative_alpha_power`, named in advance (rule 45). Reported beside the primary in both
                designs. **"Above chance" and "above the incumbent" are different claims** and only the
                first is the primary; the second requires non-overlapping intervals and is stated only if
                that holds.
  P2 FAMILY     all fourteen features with a Benjamini-Hochberg correction, reported as context. A measure
                that wins only here has not won.
  P3 PLACEBO    accuracy permuted ACROSS SUBJECTS (D1) or across pairs (D2), primary recomputed.

POWER, STATED IN ADVANCE. At 62 subjects the minimum detectable |rho| is about 0.35 at 80 % power. Under
D1's 0.8087 ceiling a true correlation of Blankertz's 0.53 attenuates to ~0.43 and is detectable; a true
0.25 attenuates to ~0.20 and is not. **So a D1 null excludes a large effect and not a modest one**, and the
write-up must say which.

VERDICT RULE, wrong direction first.

  (a) REVERSED       -- the primary's interval lies entirely on the NEGATIVE side: efficiency predicts
                        WORSE performance, contradicting the literature this design is built on.
  (b) NO PREDICTION  -- the interval includes zero in both designs. With the ceiling measured, this is a
                        REAL null and Challenge B's difficulty is not the label.
  (c) NOT INFORMATIVE-- G2 failed, or the placebo reaches the primary.
  (d) PREDICTS       -- the interval excludes zero on the positive side in at least one design. State WHICH
                        design, report the incumbent beside it, and claim superiority over the incumbent
                        only on non-overlapping intervals.

SCOPE. Stieger's task-free window is a **cued 2 s inter-trial segment, not a resting recording**, so any
comparison to Blankertz's "relax with eyes open" predictor inherits that difference (Q14).

    python -m bsde.experiments.e73_challenge_b_connectivity
"""
from __future__ import annotations

import csv
import json
import os
import sys
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
from bsde.verifier.stats import spearman                                      # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
TABLE = os.path.join(RESULTS, "stieger_features.csv")
OUT = os.path.join(RESULTS, "e73_challenge_b_connectivity.json")

PRIMARY = "wpli_alpha_global_efficiency"
INCUMBENT = "relative_alpha_power"
FEATURES = ["exponent_low", "exponent_high", "whole_head_exponent", "relative_alpha_power",
            "relative_delta_power", "spectral_edge_95", "spectral_entropy", "lempel_ziv",
            "wpli_theta", "coherence_theta", "wpli_alpha", "coherence_alpha",
            "wpli_beta", "coherence_beta", "wpli_alpha_global_efficiency",
            "wpli_alpha_clustering", "wpli_alpha_mean_degree"]
MIN_SUBJECTS, MIN_PAIRS = 30, 25
REPS = 4000
SEED = 20260731


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def _boot_rho(x, y, rng, groups=None, reps=REPS):
    x, y = np.asarray(x, float), np.asarray(y, float)
    g = np.asarray(groups) if groups is not None else np.arange(len(x))
    uniq = np.unique(g)
    v = []
    for _ in range(reps):
        drawn = rng.choice(uniq, size=len(uniq), replace=True)
        idx = np.concatenate([np.flatnonzero(g == u) for u in drawn])
        r = spearman(x[idx], y[idx])
        if np.isfinite(r):
            v.append(r)
    if len(v) < reps // 2:
        return float("nan"), float("nan")
    v = np.sort(v)
    return float(np.quantile(v, .025)), float(np.quantile(v, .975))


def _bh(pvals):
    p = np.asarray(pvals, float)
    o = np.argsort(p)
    q = np.empty_like(p)
    m = len(p)
    prev = 1.0
    for rank, i in enumerate(o[::-1]):
        prev = min(prev, p[i] * m / (m - rank))
        q[i] = prev
    return q


def main() -> int:
    if not os.path.exists(TABLE):
        print(f"MISSING {TABLE} -- run scripts/extract_stieger_features.py first")
        return 2
    rows = [r for r in csv.DictReader(open(TABLE, newline="")) if r.get("accuracy", "")]
    by = defaultdict(dict)
    for r in rows:
        by[r["subject"]][int(r["session"])] = r
    print(f"{len(rows)} sessions, {len(by)} subjects")

    rng = np.random.default_rng(SEED)
    res = {"n_sessions": len(rows), "n_subjects": len(by), "designs": {}}

    # ---- D1 between-subject
    subs = sorted(by)
    acc1 = np.array([np.mean([_f(v["accuracy"]) for v in by[s].values()]) for s in subs])
    d1 = {}
    for f in FEATURES:
        x = np.array([np.nanmean([_f(v.get(f, "")) for v in by[s].values()]) for s in subs])
        ok = np.isfinite(x) & np.isfinite(acc1)
        if ok.sum() < MIN_SUBJECTS:
            d1[f] = {"rho": float("nan"), "n": int(ok.sum())}
            continue
        r = spearman(x[ok], acc1[ok])
        lo, hi = _boot_rho(x[ok], acc1[ok], np.random.default_rng(SEED))
        d1[f] = {"rho": r, "lo": lo, "hi": hi, "n": int(ok.sum()),
                 "sd": float(np.nanstd(x[ok]))}

    # ---- D2 within-subject change
    pf, pa, pg = defaultdict(list), [], []
    for s in subs:
        for k in sorted(by[s]):
            if k + 1 in by[s]:
                pa.append(_f(by[s][k + 1]["accuracy"]) - _f(by[s][k]["accuracy"]))
                pg.append(s)
                for f in FEATURES:
                    pf[f].append(_f(by[s][k + 1].get(f, "")) - _f(by[s][k].get(f, "")))
    pa = np.array(pa)
    pg = np.array(pg)
    d2 = {}
    for f in FEATURES:
        x = np.array(pf[f], float)
        ok = np.isfinite(x) & np.isfinite(pa)
        if ok.sum() < MIN_PAIRS:
            d2[f] = {"rho": float("nan"), "n": int(ok.sum())}
            continue
        r = spearman(x[ok], pa[ok])
        lo, hi = _boot_rho(x[ok], pa[ok], np.random.default_rng(SEED + 1), groups=pg[ok])
        d2[f] = {"rho": r, "lo": lo, "hi": hi, "n": int(ok.sum())}

    g1 = (d1.get(PRIMARY, {}).get("n", 0) >= MIN_SUBJECTS
          and d2.get(PRIMARY, {}).get("n", 0) >= MIN_PAIRS)
    g2 = np.isfinite(d1.get(PRIMARY, {}).get("sd", np.nan)) and d1[PRIMARY]["sd"] > 1e-9
    print(f"\nG1 coverage {'PASS' if g1 else 'FAIL'}   G2 capability {'PASS' if g2 else 'FAIL'} "
          f"(primary sd = {d1.get(PRIMARY, {}).get('sd', float('nan')):.5g})")

    print(f"\n{'feature':<34s} {'D1 rho':>8s} {'D1 95% CI':>20s} {'D2 rho':>8s} {'D2 95% CI':>20s}")
    for f in FEATURES:
        a, b = d1.get(f, {}), d2.get(f, {})
        ca = (f"[{a['lo']:+.3f}, {a['hi']:+.3f}]" if np.isfinite(a.get("lo", np.nan)) else "--")
        cb = (f"[{b['lo']:+.3f}, {b['hi']:+.3f}]" if np.isfinite(b.get("lo", np.nan)) else "--")
        mark = " <-PRIMARY" if f == PRIMARY else (" <-incumbent" if f == INCUMBENT else "")
        print(f"{f:<34s} {a.get('rho', float('nan')):>8.3f} {ca:>20s} "
              f"{b.get('rho', float('nan')):>8.3f} {cb:>20s}{mark}")

    res["designs"] = {"D1_between_subject": d1, "D2_within_subject_change": d2}
    res["gates"] = {"g1_coverage": bool(g1), "g2_capability": bool(g2)}

    pa_ = d1.get(PRIMARY, {})
    pb_ = d2.get(PRIMARY, {})
    pos1 = np.isfinite(pa_.get("lo", np.nan)) and pa_["lo"] > 0
    pos2 = np.isfinite(pb_.get("lo", np.nan)) and pb_["lo"] > 0
    neg1 = np.isfinite(pa_.get("hi", np.nan)) and pa_["hi"] < 0
    neg2 = np.isfinite(pb_.get("hi", np.nan)) and pb_["hi"] < 0

    if not (g1 and g2):
        verdict = "NOT INFORMATIVE -- a machinery gate failed; the primary is not evaluable."
    elif neg1 or neg2:
        verdict = ("REVERSED -- alpha wPLI global efficiency predicts WORSE BCI performance, contradicting "
                   "the literature this design is built on (PMID 26529439).")
    elif pos1 or pos2:
        which = " and ".join([d for d, p in (("between-subject", pos1), ("within-subject change", pos2))
                              if p])
        inc = d1.get(INCUMBENT, {})
        beats = (np.isfinite(inc.get("hi", np.nan)) and np.isfinite(pa_.get("lo", np.nan))
                 and pa_["lo"] > inc["hi"])
        verdict = (f"PREDICTS -- alpha wPLI global efficiency predicts BCI ability in the {which} design. "
                   + ("It also separates from the incumbent on non-overlapping intervals."
                      if beats else "It does NOT separate from relative_alpha_power; 'above chance' and "
                                    "'above the incumbent' are different claims."))
    else:
        verdict = ("NO PREDICTION -- the primary's interval includes zero in both designs. With the label "
                   "ceiling measured at 0.9825 within session and 0.8087 for stable ability (E68), this is "
                   "a REAL null and not an attenuation artefact: Challenge B's difficulty is not the label. "
                   "At 62 subjects it excludes a LARGE effect (a true 0.53 would attenuate to ~0.43 and be "
                   "detectable) and does NOT exclude a modest one (~0.25 attenuates below detection).")
    print(f"\nVERDICT: {verdict}")

    fam = [(f, d1[f]["rho"], d1[f]["n"]) for f in FEATURES if np.isfinite(d1.get(f, {}).get("rho", np.nan))]
    if fam:
        z = [abs(r) * np.sqrt(max(n - 3, 1)) for _, r, n in fam]
        from math import erfc, sqrt
        p = [erfc(v / sqrt(2)) for v in z]
        q = _bh(p)
        print("\nP2 FAMILY (D1, Benjamini-Hochberg):")
        for (f, r, n), qq in sorted(zip(fam, q), key=lambda t: t[1]):
            print(f"   {f:<34s} rho {r:+.3f}  q = {qq:.4f}{'  *' if qq < 0.05 else ''}")
        res["family_bh"] = {f: {"rho": r, "q": float(qq)} for (f, r, _), qq in zip(fam, q)}

    # ---- P3 PLACEBO, registered in the docstring and ABSENT from the first run of this file.
    # It is implemented here rather than dropped: a registered arm that never executed must be reported,
    # not quietly omitted (rule 48's second half, from E37's 30 s arm). Nothing else changes -- the
    # permutation is exactly the one the registration names, and rule 48's FIRST half applies to the
    # result: a placebo cannot validate a null, so when the primary's interval includes zero this arm is
    # NOT INFORMATIVE by construction and says so instead of printing a pass.
    def _placebo(x, y, groups, seed, reps=400):
        rg = np.random.default_rng(seed)
        out = []
        for _ in range(reps):
            out.append(spearman(x, rg.permutation(y)))
        v = np.asarray([q for q in out if np.isfinite(q)])
        return (float(np.nanmedian(v)), float(np.quantile(v, .025)), float(np.quantile(v, .975)),
                float(np.mean(np.abs(v) >= abs(spearman(x, y))))) if v.size else (float("nan"),) * 4

    plac = {}
    for label, feat in (("primary", PRIMARY), ("family_bh_survivor", None)):
        if feat is None:
            surv = [f for f, d in res.get("family_bh", {}).items() if d["q"] < 0.05]
            if not surv:
                continue
            feat = surv[0]
        xa = np.array([np.nanmean([_f(v.get(feat, "")) for v in by[s].values()]) for s in subs])
        oka = np.isfinite(xa) & np.isfinite(acc1)
        pm, plo, phi, pfrac = _placebo(xa[oka], acc1[oka], None, SEED + 7)
        real = d1.get(feat, {}).get("rho", float("nan"))
        null_primary = not (np.isfinite(d1.get(feat, {}).get("lo", np.nan))
                            and (d1[feat]["lo"] > 0 or d1[feat]["hi"] < 0))
        plac[label] = {"feature": feat, "real_D1_rho": real, "placebo_median": pm,
                       "placebo_ci": [plo, phi], "frac_placebo_at_least_as_extreme": pfrac,
                       "informative": bool(not null_primary)}
        print(f"\nP3 PLACEBO ({label}: {feat}) accuracy permuted across subjects, D1")
        print(f"    real rho {real:+.3f}   placebo median {pm:+.3f} [{plo:+.3f}, {phi:+.3f}]   "
              f"fraction of permutations at least as extreme = {pfrac:.4f}")
        if null_primary:
            print("    NOT INFORMATIVE -- the real effect's interval includes zero, so there is nothing "
                  "for a permutation to fail to reproduce (rule 48).")
    res["placebo_P3"] = plac

    res["verdict"] = verdict
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
