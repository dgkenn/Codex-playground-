#!/usr/bin/env python3
"""E140 -- is E36's phase/amplitude split a DRUG-identity split, or a DATA-QUALITY-sensitivity split?

REGISTERED BEFORE ANY ADJUSTED AUC HAS BEEN COMPUTED. Successor to E36 and to E139. The instrument that
changed is named in the ledger row and again below; no threshold, cohort or horizon from a failed test has
been moved.

=========================================================================================================
WHAT E139 FOUND WHILE FAILING
=========================================================================================================
E139 carried `pctGoodSamples` as a fourteenth feature, purely as a placebo, and it failed its own gate:

    among the 115 UNRESPONSIVE scalp blocks, recording quality identifies the agent at
    |AUC - 0.5| = **0.2565**  (AUC 0.2435; dexmedetomidine median 0.9755, propofol 0.9954)

verified against an independent Mann-Whitney written outside the project's own statistics module. That
single number is larger than the drug legibility of **9 of the 12 features**, and larger than either
family's mean. E139 was correctly voided.

**But the number does not only void E139.** E35 and E36 computed the same drug-identification AUCs on the
same rows with no quality control at all, and E36's headline -- the phase family leaks 0.000-0.128 while
the amplitude family leaks 0.217-0.368, the unique maximum of all 495 partitions at p = 0.002 -- is a
statement about a contrast that quality could manufacture. E36 was careful about multiplicity, about
family assignment, and about capability; it was not careful about this, because nobody had measured it.

The mechanism is not speculative. wPLI is *designed* to be insensitive to amplitude artefact -- that is
what the weighted-phase-lag construction is for -- while `EffDim`, `NmlzCmplx`, `allEnvCorr` and the four
band powers are all computed from broadband amplitude, which is exactly where dropped and artefactual
samples live. **A family split by amplitude-sensitivity and a family split by quality-sensitivity are the
same partition of these thirteen columns.** So the two explanations are not merely both available; they
predict the identical grouping, and only an adjustment can separate them.

=========================================================================================================
THE INSTRUMENT CHANGE
=========================================================================================================
Drug legibility is recomputed with recording quality removed, THREE independent ways, because any one
adjustment can be wrong in its own particular manner and agreement across three is worth more than
precision in one (rule 23's shape applied to an estimator rather than to code):

  A1  RANK RESIDUAL.  rank(feature) is regressed on rank(pctGoodSamples) across the 115 blocks and the
      AUC is taken on the residual. Uses every block; assumes the quality dependence is monotone.
  A2  CALIPER MATCH.  1:1 greedy matching of dexmedetomidine to propofol blocks within 0.01 of quality,
      giving 32 pairs (checked before registration). Uses a third of the data; assumes nothing about
      functional form.
  A3  STRATIFIED.  Quality quintiles, AUC within each, size-weighted (van Elteren's shape). Degenerate
      strata -- one arm absent -- are dropped and counted, never treated as AUC 0.5.

**A2 CARRIES ITS RULE-35 CONTROL, which is not optional.** Matching discards 83 of 115 blocks, and
discarding data attenuates things by itself. So beside the matched estimate, 1,000 subsamples of the SAME
SIZE are drawn WITHOUT matching on quality. If the gap collapses in the matched set but sits comfortably
inside the size-only null, the collapse is sample size, not quality. Rule 35 exists because this control
put a previous project's null at ~100 % everywhere and made every departure readable.

=========================================================================================================
GATE Q -- and it can fail, which is the point
=========================================================================================================
For each adjustment, `pctGoodSamples`'s OWN drug legibility must fall below **0.05** after that
adjustment is applied to it. An adjustment that leaves quality legible cannot be used to argue that a
feature's legibility is or is not quality. Adjustments failing GATE Q are reported and excluded from the
primary; if all three fail, no verdict is issued.

G1  MANIFEST. >= 6 patients per arm contributing unresponsive scalp blocks (observed at registration:
    8 propofol, 7 dexmedetomidine). This is a between-patient contrast and does NOT require a patient to
    contribute both states, which is the requirement E139's G1 imposed and failed on; that is an estimand
    change, stated here rather than a bar being lowered, and it costs the paired structure.
G2  VARIATION (rule 32). Every feature must vary in both arms within the stratum compared.

=========================================================================================================
PRIMARY, WRONG-DIRECTION BRANCH WRITTEN FIRST (rule 37)
=========================================================================================================
    GAP  =  mean drug_leg(AMPLITUDE)  -  mean drug_leg(PHASE)

unadjusted, recomputed in this file from E139's numbers (+0.1968 vs +0.1056, GAP = +0.0913). Families are
E36's and are NOT revisable here.

**IF THE GAP SURVIVES** -- adjusted GAP retains at least half of the unadjusted value under every
adjustment that passes GATE Q, with a patient-clustered interval excluding 0 -- then E36's split is not a
quality artefact and comes out of this audit stronger than it went in, because the most obvious
alternative explanation has been removed rather than ignored.

**IF THE GAP COLLAPSES** -- adjusted GAP below half the unadjusted value, while the rule-35 size-only
control shows the matched-set collapse is NOT reproduced by sample-size loss -- then E36's family split is
substantially a data-quality-sensitivity split. The phase family's agent-invariance would then be, in
part, insensitivity to bad samples, and **every downstream use of E36 must be re-derived, not carried
forward** (rule 2). That includes E36's central recommendation, the amplitude+phase composite, whose whole
rationale is that the two families differ in what they leak.

**REGISTERED PREDICTION: COLLAPSE.** Stated against this project's own prior result, which is the correct
direction to bet, and for reasons that were available before the run: the quality signal (0.2565) is
nearly three times the gap it would have to manufacture (0.0913), and the amplitude/phase partition is
co-extensive with the quality-sensitive/quality-robust partition on these columns. If the gap survives
anyway, that is a genuine strengthening of E36 and will be reported as one.

SECONDARY, NO VERDICT ATTACHED TO EITHER.
  S1  E139's LAMBDA recomputed with the adjusted drug half. E139's G1 failure is not relitigated here and
      LAMBDA is reported as description only.
  S2  E139 observed rho(drug-free sleep transfer AUC, -drug_leg) = **-0.2448** -- the features leaking the
      MOST agent identity transferred BEST to natural sleep, the direction opposite to registration. It is
      recomputed against the adjusted drug legibility and reported, because if it survives it is a
      substantive objection to Challenge A's acceptance condition itself: minimising drug-identification
      information would not be the same thing as generalising beyond the drug.

FALSIFICATION. If every adjusted GAP interval spans zero AND the size-only control interval also spans
zero, the deposit cannot resolve the question at 15 patients and that is the report.

WHAT WAS ALREADY SEEN (rule 41). E139's full output, quoted above and in the ledger; the quality medians
per arm; the common-support range (dex 0.8955-0.9954 inside propofol's 0.7185-1.0000, so all 56 dex blocks
are on support and 26 of 59 propofol blocks are); and the matched-pair counts at four calipers
(0.002 -> 26, 0.005 -> 29, 0.010 -> 32, 0.020 -> 41), which is how the 0.01 caliper was chosen. No
adjusted feature AUC has been computed.

    python bsde/src/bsde/experiments/e140_is_the_family_split_data_quality.py
"""
from __future__ import annotations

import csv
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from bsde.verifier.stats import auc, auc_abs, cluster_bootstrap_ci, spearman   # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
TABLE = os.path.join(RESULTS, "krause_dexprosleep_allData.csv")
E139 = os.path.join(RESULTS, "e139_challenge_a_single_statistic.json")
OUT = os.path.join(RESULTS, "e140_family_split_quality_audit.json")

PHASE = ["frontwPLI", "backwPLI", "longwPLI", "allwPLI"]
AMPLITUDE = ["EffDim", "NmlzCmplx", "allEnvCorr", "AvgDelta", "AvgAlpha", "AvgGamma",
             "frontalDelta", "frontalAlpha"]
FEATURES = AMPLITUDE + PHASE
Q = "pctGoodSamples"
CALIPER = 0.01
GATE_Q = 0.05


def _f(s):
    try:
        v = float(s)
        return v if math.isfinite(v) else float("nan")
    except (TypeError, ValueError):
        return float("nan")


def load():
    """The 115 unresponsive scalp blocks: the stratum E35/E36's drug contrast is computed in."""
    out = []
    for r in csv.DictReader(open(TABLE, newline="")):
        if r["Subdural"] != "0" or r["label"] not in ("U", "U_dex"):
            continue
        # quality is stored twice on purpose: under "q" as the adjustment variable, and under its own
        # column name so it can be pushed through the identical code path as a feature for GATE Q.
        out.append({"pid": r["patientID"], "arm": 1 if r["label"] == "U_dex" else 0,
                    "q": _f(r[Q]), Q: _f(r[Q]), **{c: _f(r.get(c, "")) for c in FEATURES}})
    return [r for r in out if math.isfinite(r["q"])]


def _ranks(v):
    v = np.asarray(v, float)
    o = np.argsort(v, kind="mergesort")
    r = np.empty(len(v), float)
    r[o] = np.arange(1, len(v) + 1)
    # average ties so a column with repeated values is not given a spurious ordering
    for u in np.unique(v):
        m = v == u
        if m.sum() > 1:
            r[m] = r[m].mean()
    return r


def leg_raw(rows, col):
    y = [r["arm"] for r in rows if math.isfinite(r[col])]
    x = [r[col] for r in rows if math.isfinite(r[col])]
    if len(set(y)) < 2 or len(set(x)) < 2:
        return float("nan")
    return auc_abs(y, x) - 0.5


def leg_a1(rows, col):
    """Rank residual: rank(feature) with rank(quality) projected out, then AUC."""
    ok = [r for r in rows if math.isfinite(r[col])]
    if len(ok) < 8:
        return float("nan")
    y = [r["arm"] for r in ok]
    if len(set(y)) < 2:
        return float("nan")
    rf, rq = _ranks([r[col] for r in ok]), _ranks([r["q"] for r in ok])
    A = np.c_[np.ones(len(rq)), rq]
    beta, *_ = np.linalg.lstsq(A, rf, rcond=None)
    res = rf - A @ beta
    if len(set(np.round(res, 12))) < 2:
        return float("nan")
    return auc_abs(y, res) - 0.5


def _match(rows, caliper=CALIPER):
    """Greedy 1:1 quality matching of dex blocks to propofol blocks. Deterministic given the row order."""
    dex = [r for r in rows if r["arm"] == 1]
    prop = [r for r in rows if r["arm"] == 0]
    pool = list(prop)
    out = []
    for d in sorted(dex, key=lambda r: r["q"]):
        cand = [p for p in pool if abs(p["q"] - d["q"]) <= caliper]
        if cand:
            p = min(cand, key=lambda p: abs(p["q"] - d["q"]))
            pool.remove(p)
            out += [d, p]
    return out


def leg_a3(rows, col, k=5):
    """Size-weighted AUC within quality quintiles; degenerate strata dropped and counted by the caller."""
    ok = [r for r in rows if math.isfinite(r[col])]
    if len(ok) < 10:
        return float("nan")
    qs = np.quantile([r["q"] for r in ok], np.linspace(0, 1, k + 1))
    num = den = 0.0
    for i in range(k):
        lo, hi = qs[i], qs[i + 1]
        s = [r for r in ok if (lo <= r["q"] <= hi if i == k - 1 else lo <= r["q"] < hi)]
        y = [r["arm"] for r in s]
        x = [r[col] for r in s]
        if len(set(y)) < 2 or len(set(x)) < 2:
            continue
        num += len(s) * (auc(y, x) - 0.5)
        den += len(s)
    if den == 0:
        return float("nan")
    return abs(num / den)


def gap(rows, fn):
    a = [fn(rows, c) for c in AMPLITUDE]
    p = [fn(rows, c) for c in PHASE]
    return float(np.nanmean(a) - np.nanmean(p))


def main(argv=None) -> int:
    rng = np.random.default_rng(140)
    rows = load()
    out = {"experiment": "E140", "n_blocks": len(rows)}

    # ---- G1 MANIFEST ------------------------------------------------------------------------------
    pats = {a: len({r["pid"] for r in rows if r["arm"] == a}) for a in (0, 1)}
    g1 = pats[0] >= 6 and pats[1] >= 6
    print(f"G1 MANIFEST  unresponsive scalp blocks={len(rows)}  patients prop={pats[0]} dex={pats[1]}"
          f"  -> {'PASS' if g1 else 'FAIL'}")
    # ---- G2 VARIATION -----------------------------------------------------------------------------
    dropped = [c for c in FEATURES
               if any(len({r[c] for r in rows if r["arm"] == a and math.isfinite(r[c])}) < 2
                      for a in (0, 1))]
    print(f"G2 VARIATION  constant in an arm: {dropped or 'none'}")
    out["G1"] = {"pass": bool(g1), "patients": pats}
    out["G2"] = {"dropped": dropped}

    # ---- unadjusted baseline ----------------------------------------------------------------------
    base = {c: leg_raw(rows, c) for c in FEATURES + [Q]}
    g0 = gap(rows, leg_raw)
    print(f"\nUNADJUSTED   mean AMPLITUDE={np.nanmean([base[c] for c in AMPLITUDE]):+.4f}  "
          f"mean PHASE={np.nanmean([base[c] for c in PHASE]):+.4f}  GAP={g0:+.4f}")
    print(f"             quality own legibility = {base[Q]:+.4f}")

    matched = _match(rows)
    print(f"             caliper {CALIPER} -> {len(matched) // 2} pairs ({len(matched)} blocks)")

    adjust = {"A1_rank_residual": (rows, leg_a1),
              "A2_caliper_matched": (matched, leg_raw),
              "A3_stratified": (rows, leg_a3)}

    # ---- GATE Q -----------------------------------------------------------------------------------
    print(f"\nGATE Q  quality's own legibility after each adjustment must be < {GATE_Q}")
    passed = []
    out["gateQ"] = {}
    for name, (rs, fn) in adjust.items():
        qv = fn(rs, Q)
        ok = math.isfinite(qv) and qv < GATE_Q
        print(f"   {name:20s} quality legibility = {qv:+.4f}  -> {'PASS' if ok else 'FAIL (excluded)'}")
        out["gateQ"][name] = {"quality_leg": qv, "pass": bool(ok)}
        if ok:
            passed.append(name)

    # ---- primary ----------------------------------------------------------------------------------
    print(f"\n{'feature':16s} {'family':10s} {'raw':>8s} {'A1':>8s} {'A2':>8s} {'A3':>8s}")
    per = {}
    for c in FEATURES:
        v = {"raw": base[c], "A1_rank_residual": leg_a1(rows, c),
             "A2_caliper_matched": leg_raw(matched, c), "A3_stratified": leg_a3(rows, c),
             "family": "PHASE" if c in PHASE else "AMPLITUDE"}
        per[c] = v
        print(f"{c:16s} {v['family']:10s} {v['raw']:+8.4f} {v['A1_rank_residual']:+8.4f} "
              f"{v['A2_caliper_matched']:+8.4f} {v['A3_stratified']:+8.4f}")
    out["per_feature"] = per
    out["unadjusted_gap"] = g0

    print(f"\nPRIMARY  GAP = mean AMPLITUDE - mean PHASE, patient-clustered bootstrap (1,000 reps)")
    pids = np.array([r["pid"] for r in rows])
    mpids = np.array([r["pid"] for r in matched])
    res = {}
    for name in adjust:
        rs, fn = adjust[name]
        g = gap(rs, fn)
        pp = mpids if name.startswith("A2") else pids
        lo, hi, nok = cluster_bootstrap_ci(
            lambda ix, rs=rs, fn=fn: gap([rs[i] for i in ix], fn), pp, rng, reps=1000)
        retained = g / g0 if g0 else float("nan")
        res[name] = {"gap": g, "ci": [lo, hi], "retained_fraction": retained, "n_ok": nok,
                     "gate_q_pass": name in passed}
        mark = "" if name in passed else "   [EXCLUDED by GATE Q]"
        print(f"   {name:20s} GAP={g:+.4f} [{lo:+.4f}, {hi:+.4f}]  retains {retained:5.1%} of "
              f"{g0:+.4f}{mark}")
    out["primary"] = res

    # ---- rule 35: the size-only control for A2 -----------------------------------------------------
    n_pairs = len(matched) // 2
    ctrl = []
    dex = [r for r in rows if r["arm"] == 1]
    prop = [r for r in rows if r["arm"] == 0]
    for _ in range(1000):
        s = ([dex[i] for i in rng.choice(len(dex), size=min(n_pairs, len(dex)), replace=False)] +
             [prop[i] for i in rng.choice(len(prop), size=min(n_pairs, len(prop)), replace=False)])
        v = gap(s, leg_raw)
        if math.isfinite(v):
            ctrl.append(v)
    ctrl = np.sort(np.asarray(ctrl))
    a2 = res["A2_caliper_matched"]["gap"]
    frac = float(np.mean(ctrl <= a2))
    print(f"\nRULE-35 CONTROL  1,000 size-matched subsamples NOT matched on quality "
          f"({n_pairs} per arm)")
    print(f"   size-only GAP null: median {np.median(ctrl):+.4f}, "
          f"[{np.quantile(ctrl, .025):+.4f}, {np.quantile(ctrl, .975):+.4f}]")
    print(f"   matched-set GAP {a2:+.4f} sits at the {frac:.1%} point of that null "
          f"-> the collapse is {'NOT ' if frac >= 0.05 else ''}beyond sample-size loss")
    out["rule35_control"] = {"n_per_arm": n_pairs, "null_median": float(np.median(ctrl)),
                             "null_ci": [float(np.quantile(ctrl, .025)),
                                         float(np.quantile(ctrl, .975))],
                             "matched_gap": a2, "frac_null_below": frac}

    # ---- verdict ------------------------------------------------------------------------------------
    if not passed or not g1:
        verdict = ("NO VERDICT -- " + ("G1 failed" if not g1 else
                                       "every adjustment failed GATE Q, so none can speak to the question"))
    else:
        rets = [res[n]["retained_fraction"] for n in passed]
        excl = [res[n]["ci"][0] > 0 for n in passed]
        if all(r >= 0.5 for r in rets) and all(excl):
            verdict = ("SURVIVES -- E36's family split is not a data-quality artefact. Every adjustment "
                       "passing GATE Q retains at least half the unadjusted gap with an interval "
                       "excluding zero. The registered prediction (COLLAPSE) is WRONG and E36 comes out "
                       "of the audit stronger.")
        elif all(r < 0.5 for r in rets) and frac < 0.05:
            verdict = ("COLLAPSES -- E36's family split is substantially a data-quality-sensitivity "
                       "split, and the collapse is not reproduced by sample-size loss. Every downstream "
                       "use of E36, including its amplitude+phase composite recommendation, must be "
                       "re-derived rather than carried forward (rule 2).")
        else:
            verdict = ("INDETERMINATE -- adjustments disagree or intervals span zero at 15 patients. "
                       f"retained fractions {['%.2f' % r for r in rets]}, "
                       f"rule-35 control frac {frac:.3f}.")
    print(f"\nVERDICT: {verdict}")
    out["verdict"] = verdict

    # ---- S1 / S2, description only ------------------------------------------------------------------
    try:
        e139 = json.load(open(E139))
        adj = passed[0] if passed else None
        if adj:
            rs, fn = adjust[adj]
            s1 = {c: e139["P1_lambda"][c]["state_leg"] - fn(rs, c)
                  for c in FEATURES if c in e139.get("P1_lambda", {})}
            out["S1_lambda_adjusted"] = {"adjustment": adj, "lambda": s1}
            print(f"\nS1 (description only) LAMBDA with the {adj} drug half, E139's state half unchanged:")
            for c in sorted(s1, key=lambda c: -s1[c]):
                print(f"   {c:16s} {s1[c]:+.4f}")
            tr = e139.get("P3", {}).get("transfer_auc", {})
            ok = [c for c in s1 if math.isfinite(tr.get(c, float('nan')))]
            r2 = spearman([tr[c] for c in ok], [-fn(rs, c) for c in ok])
            out["S2_transfer_rho_adjusted"] = {"rho": r2, "n": len(ok), "e139_rho": -0.2448}
            print(f"\nS2 (description only) rho(sleep transfer AUC, -adjusted drug_leg) over {len(ok)} "
                  f"features = {r2:+.4f}   (E139 unadjusted: -0.2448)")
    except Exception as e:                                                       # noqa: BLE001
        out["S1_S2_error"] = f"{type(e).__name__}: {e}"

    with open(OUT, "w") as fh:
        json.dump(out, fh, indent=1, sort_keys=True, allow_nan=True)
    print(f"\n   wrote {os.path.relpath(OUT, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
