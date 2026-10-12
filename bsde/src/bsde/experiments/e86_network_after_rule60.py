"""E86 -- Challenge B's network question, with a primary that has been SHOWN to escape mean connectivity.

REGISTERED BEFORE ANY FEATURE HAS BEEN RELATED TO ANY ACCURACY on `stieger_graph62.csv`. The rule-60
check reported below was run on a PARTIAL version of that table (113 sessions, 38 subjects, extraction
still running) and is a feature-versus-feature correlation matrix only -- no accuracy column was touched.
The analysis itself runs on the completed table.

=========================================================================================================
THE RULE-60 CHECK, AND IT REFUTED THIS PROJECT'S OWN DIAGNOSIS
=========================================================================================================
E73 returned Challenge B's first interpretable null on `wpli_alpha_global_efficiency`, and the finding
underneath it was that the primary correlated with `wpli_alpha_mean_degree` at +0.9962 -- it was mean
connectivity strength restated. The mechanism was then located: the extractor used a **ten-channel**
montage, and on a near-complete 10-node weighted graph nearly every shortest path is the direct edge.
`extract_stieger_graph62.py` was written to fix that, on the expectation that 62 nodes would give a graph
measure room to differ.

**It does not.** On the 62-channel graph, across 38 subject means:

    deg vs ge            rho +0.9702      <- global efficiency is STILL mean strength restated
    deg vs cl_norm       rho -0.8278
    deg vs modularity    rho -0.7634
    deg vs smallworld    rho -0.7359
    deg vs strength_cv   rho -0.7203
    deg vs alpha_prom    rho +0.5078
    deg vs ge_norm       rho +0.2570      <- escapes
    deg vs iaf           rho +0.2356      <- escapes (different family entirely)

**So the montage was not the mechanism, or not the whole of it: unthresholded weighted global efficiency
is mean strength at 62 nodes as surely as at 10.** That is a stronger and more general statement than
E73's, and it contradicts the diagnosis this project wrote down when rule 60 was created. The correction
belongs on the record beside the rule.

What does escape is **normalisation against a null that preserves the weight distribution**. `ge_norm` is
global efficiency divided by its mean over 20 weight-shuffled graphs; shuffling preserves the multiset of
edge weights exactly and destroys topology, so overall strength cancels by construction -- and the measured
+0.2570 confirms that it does, rather than assuming it.

ALSO ON THE RECORD, because it decides the family: `cl_norm`, `smallworld` and `strength_cv` correlate
with each other at +0.8729 to +0.9652. **They are one construct with three names, so only ONE of them is
tested** -- `cl_norm`, chosen because it is the direct null-normalised twin of a measure E73 already
reported. Testing all three would inflate the family count while measuring one thing (rule 28).

=========================================================================================================
PRIMARY
=========================================================================================================
    P   `ge_norm`, **predicted POSITIVE**, following PMID 26529439's report that resting global efficiency
        correlates positively with motor-imagery classification accuracy. Two designs, identical to E73's
        so the results are directly comparable:

        D1  BETWEEN-SUBJECT   subject-mean feature against subject-mean accuracy. Capped near
                              sqrt(R2) = 0.8087 by E68's stable-ability reliability.
        D2  WITHIN-SUBJECT    consecutive-session change in feature against change in accuracy,
                              subject-clustered. Capped near 0.9478.

    FAMILY, as context only and never a result on its own (E73's formulation, carried over): `cl_norm`,
    `modularity`, `iaf`, `alpha_prom`, with Benjamini-Hochberg at q = 0.05 over those four plus the
    primary. `ge`, `cl`, `deg` and the two redundant twins are reported DESCRIPTIVELY and are excluded
    from the family, because `ge`/`deg` are the thing being escaped and testing them would be E73 again.

POWER, stated in advance and unchanged from E73 because the deposit and designs are unchanged: at ~60
subjects the minimum detectable |rho| is about 0.35 at 80 % power, so under D1's 0.8087 ceiling a true
0.53 attenuates to ~0.43 and is detectable while a true 0.25 is not. **A D1 null excludes a large effect
and not a modest one, and the write-up must say which.**

GATES (rule 40):

    G1  COVERAGE    >= 30 subjects for D1 and >= 25 consecutive-session pairs for D2.
    G2  CAPABILITY  `ge_norm` must vary non-degenerately across subjects (rule 53) -- else a null is about
                    the extractor rather than the brain.
    G3  ESCAPE HOLDS ON THE FULL TABLE. The rule-60 check above was run on a partial extraction. It is
                    **re-run here on the completed table and gates the primary**: |rho(ge_norm, deg)| must
                    stay below 0.90. If widening the sample makes the primary collapse back onto mean
                    strength, this is E73 again and the verdict is ABSENT, not a null.

PLACEBO: accuracy permuted across subjects (D1) or across pairs (D2), primary recomputed, 500 draws. A
primary inside the central 95 % is withdrawn.

VERDICT, wrong direction first (rule 37):

    (a) interval excludes 0 NEGATIVE -> REVERSED. Normalised efficiency predicts WORSE performance,
        contradicting PMID 26529439. Report as a contradiction, not as a detection.
    (b) interval includes 0 in both designs -> NO PREDICTION. With E68's ceiling measured, a real null.
    (c) interval excludes 0 POSITIVE in at least one design -> PREDICTS. State WHICH design, report the
        incumbent beside it, and claim superiority over the incumbent only on non-overlapping intervals.

    python -m bsde.experiments.e86_network_after_rule60
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

GRAPH_TABLE = os.path.join(RESULTS, "stieger_graph62.csv")
ACC_TABLE = os.path.join(RESULTS, "stieger_features.csv")
OUT = os.path.join(RESULTS, "e86_network_after_rule60.json")

PRIMARY = "ge_norm"
FAMILY = ["cl_norm", "modularity", "iaf", "alpha_prom"]
DESCRIPTIVE = ["ge", "cl", "deg", "smallworld", "strength_cv"]
ESCAPE_FROM = "deg"
ESCAPE_MAX = 0.90
MIN_SUBJECTS, MIN_PAIRS = 30, 25
REPS = 4000
PLACEBO_DRAWS = 500
SEED = 20260731


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def spearman(a, b):
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() < 8 or len(set(a[ok].tolist())) < 2 or len(set(b[ok].tolist())) < 2:
        return float("nan")
    from scipy.stats import spearmanr
    return float(spearmanr(a[ok], b[ok]).statistic)


def boot_rho(x, y, seed, groups=None, reps=REPS):
    rng = np.random.default_rng(seed)
    out = []
    if groups is None:
        n = x.size
        for _ in range(reps):
            i = rng.integers(0, n, n)
            r = spearman(x[i], y[i])
            if np.isfinite(r):
                out.append(r)
    else:
        uniq = np.unique(groups)
        for _ in range(reps):
            drawn = rng.choice(uniq, size=uniq.size, replace=True)
            idx = np.concatenate([np.flatnonzero(groups == g) for g in drawn])
            r = spearman(x[idx], y[idx])
            if np.isfinite(r):
                out.append(r)
    if len(out) < 50:
        return float("nan"), float("nan")
    out = np.sort(out)
    return float(np.quantile(out, .025)), float(np.quantile(out, .975))


def bh(pvals):
    m = len(pvals)
    order = np.argsort(pvals)
    q = np.empty(m)
    prev = 1.0
    for rank in range(m - 1, -1, -1):
        i = order[rank]
        prev = min(prev, pvals[i] * m / (rank + 1))
        q[i] = prev
    return q


def main() -> int:
    for p in (GRAPH_TABLE, ACC_TABLE):
        if not os.path.exists(p):
            print(f"ABSENT: {p}"); return 2
    acc = {}
    for r in csv.DictReader(open(ACC_TABLE, newline="")):
        if r.get("accuracy"):
            acc[(r["subject"], str(int(r["session"])))] = _f(r["accuracy"])
    rows = [r for r in csv.DictReader(open(GRAPH_TABLE, newline=""))]
    by = defaultdict(dict)
    for r in rows:
        k = (r["subject"], str(int(r["session"])))
        if k in acc:
            by[r["subject"]][int(r["session"])] = (r, acc[k])
    subs = sorted(by)
    feats = [PRIMARY] + FAMILY + DESCRIPTIVE
    res = {"n_sessions": len(rows), "n_subjects": len(subs), "designs": {}, "gates": {}}
    print(f"{len(rows)} graph sessions, {len(subs)} subjects joined to an accuracy")

    # G3: the escape must survive the full table
    m_pri = np.array([np.nanmean([_f(v[0][PRIMARY]) for v in by[s].values()]) for s in subs])
    m_esc = np.array([np.nanmean([_f(v[0][ESCAPE_FROM]) for v in by[s].values()]) for s in subs])
    esc = spearman(m_pri, m_esc)
    res["gates"]["G3_rho_primary_vs_" + ESCAPE_FROM] = esc
    res["gates"]["G3_pass"] = bool(np.isfinite(esc) and abs(esc) < ESCAPE_MAX)
    print(f"G3 escape     rho({PRIMARY}, {ESCAPE_FROM}) = {esc:+.4f}   "
          f"{'PASS' if res['gates']['G3_pass'] else 'FAIL -- this is E73 again'}")

    d1, d2 = {}, {}
    acc1 = np.array([np.nanmean([v[1] for v in by[s].values()]) for s in subs])
    for f in feats:
        x = np.array([np.nanmean([_f(v[0].get(f, "")) for v in by[s].values()]) for s in subs])
        ok = np.isfinite(x) & np.isfinite(acc1)
        if ok.sum() < MIN_SUBJECTS:
            d1[f] = {"rho": float("nan"), "n": int(ok.sum())}
            continue
        lo, hi = boot_rho(x[ok], acc1[ok], SEED)
        d1[f] = {"rho": spearman(x[ok], acc1[ok]), "lo": lo, "hi": hi, "n": int(ok.sum()),
                 "sd": float(np.nanstd(x[ok]))}

    pa, pg, pf = [], [], defaultdict(list)
    for s in subs:
        for k in sorted(by[s]):
            if k + 1 in by[s]:
                pa.append(by[s][k + 1][1] - by[s][k][1])
                pg.append(s)
                for f in feats:
                    pf[f].append(_f(by[s][k + 1][0].get(f, "")) - _f(by[s][k][0].get(f, "")))
    pa, pg = np.asarray(pa, float), np.asarray(pg)
    for f in feats:
        x = np.asarray(pf[f], float)
        ok = np.isfinite(x) & np.isfinite(pa)
        if ok.sum() < MIN_PAIRS:
            d2[f] = {"rho": float("nan"), "n": int(ok.sum())}
            continue
        lo, hi = boot_rho(x[ok], pa[ok], SEED + 1, groups=pg[ok])
        d2[f] = {"rho": spearman(x[ok], pa[ok]), "lo": lo, "hi": hi, "n": int(ok.sum())}

    g1 = d1.get(PRIMARY, {}).get("n", 0) >= MIN_SUBJECTS and d2.get(PRIMARY, {}).get("n", 0) >= MIN_PAIRS
    g2 = np.isfinite(d1.get(PRIMARY, {}).get("sd", np.nan)) and d1[PRIMARY]["sd"] > 1e-9
    res["gates"].update({"G1_pass": bool(g1), "G2_pass": bool(g2),
                         "G1_d1_n": d1.get(PRIMARY, {}).get("n", 0),
                         "G1_d2_n": d2.get(PRIMARY, {}).get("n", 0)})
    print(f"G1 coverage   D1 n={res['gates']['G1_d1_n']}, D2 n={res['gates']['G1_d2_n']}   "
          f"{'PASS' if g1 else 'FAIL'}")
    print(f"G2 capability {PRIMARY} sd = {d1.get(PRIMARY, {}).get('sd', float('nan')):.5g}   "
          f"{'PASS' if g2 else 'FAIL'}")

    print(f"\n{'feature':<16s} {'D1 rho':>8s} {'D1 95% CI':>20s} {'D2 rho':>8s} {'D2 95% CI':>20s}")
    for f in feats:
        a, b = d1.get(f, {}), d2.get(f, {})
        tag = " <-PRIMARY" if f == PRIMARY else (" (descriptive)" if f in DESCRIPTIVE else "")
        print(f"{f:<16s} {a.get('rho', float('nan')):+8.3f} "
              f"[{a.get('lo', float('nan')):+8.3f}, {a.get('hi', float('nan')):+8.3f}] "
              f"{b.get('rho', float('nan')):+8.3f} "
              f"[{b.get('lo', float('nan')):+8.3f}, {b.get('hi', float('nan')):+8.3f}]{tag}")
    res["designs"] = {"D1": d1, "D2": d2}

    if not (g1 and g2 and res["gates"]["G3_pass"]):
        why = ("the primary collapsed back onto mean strength" if not res["gates"]["G3_pass"]
               else "coverage" if not g1 else "capability")
        print(f"\nGATE FAILED ({why}) -- the primary is not evaluated. Verdict ABSENT (rule 31).")
        res["verdict"] = "GATE-FAILED"
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    pos = [dn for dn, d in (("D1", d1), ("D2", d2))
           if np.isfinite(d[PRIMARY].get("lo", np.nan)) and d[PRIMARY]["lo"] > 0]
    neg = [dn for dn, d in (("D1", d1), ("D2", d2))
           if np.isfinite(d[PRIMARY].get("hi", np.nan)) and d[PRIMARY]["hi"] < 0]

    # placebo on the primary, D1
    x = np.array([np.nanmean([_f(v[0][PRIMARY]) for v in by[s].values()]) for s in subs])
    ok = np.isfinite(x) & np.isfinite(acc1)
    rng = np.random.default_rng(SEED + 2)
    pl = np.sort([r for r in (spearman(x[ok], rng.permutation(acc1[ok]))
                              for _ in range(PLACEBO_DRAWS)) if np.isfinite(r)])
    p_lo, p_hi = float(np.quantile(pl, .025)), float(np.quantile(pl, .975))
    inside = bool(p_lo <= d1[PRIMARY]["rho"] <= p_hi)
    res["placebo_D1"] = {"lo": p_lo, "hi": p_hi, "inside": inside}
    print(f"\nPLACEBO D1  accuracy permuted across subjects: [{p_lo:+.3f}, {p_hi:+.3f}]   "
          f"{'primary INSIDE' if inside else 'primary outside'}")

    if neg:
        verdict = (f"REVERSED in {neg} -- normalised global efficiency predicts WORSE BCI performance, "
                   f"contradicting PMID 26529439. A contradiction, not a detection.")
    elif pos and not inside:
        verdict = (f"PREDICTS in {pos}. Report the incumbent beside it; 'above chance' and 'above the "
                   f"incumbent' are different claims.")
    elif pos and inside:
        verdict = "WITHDRAWN-BY-PLACEBO -- the primary lies inside the permuted-accuracy distribution."
    else:
        verdict = ("NO PREDICTION -- the primary's interval includes zero in both designs. With E68's "
                   "ceiling measured (0.9652 within session, 0.8087 stable-ability) this is a REAL null. "
                   "At ~60 subjects it excludes a LARGE effect and does NOT exclude a modest one.")

    fam = [(f, d1[f]["rho"], d1[f]["n"]) for f in [PRIMARY] + FAMILY
           if np.isfinite(d1.get(f, {}).get("rho", np.nan))]
    if fam:
        from math import erfc, sqrt
        p = [erfc(abs(r) * np.sqrt(max(n - 3, 1)) / sqrt(2)) for _, r, n in fam]
        q = bh(p)
        print("\nFAMILY (D1, BH q=0.05; a measure that wins only here has not won)")
        for (f, r, _), qq in sorted(zip(fam, q), key=lambda t: t[1]):
            print(f"   {f:<16s} rho {r:+.3f}  q = {qq:.4f}{'  *' if qq < 0.05 else ''}")
        res["family_bh"] = {f: {"rho": r, "q": float(qq)} for (f, r, _), qq in zip(fam, q)}

    res["verdict"] = verdict
    print(f"\nVERDICT: {verdict}")
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
